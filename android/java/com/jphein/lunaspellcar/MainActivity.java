package com.jphein.lunaspellcar;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.util.Base64;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** Hosts the Spell Car web app in a WebView and bridges native text-to-speech and file saving. */
public class MainActivity extends Activity implements TextToSpeech.OnInitListener {

    private WebView web;
    private TextToSpeech tts;
    private volatile boolean ttsReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(0xFF2B1658);
        getWindow().setNavigationBarColor(0xFF1B0F38);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setTextZoom(100);
        web.setBackgroundColor(0xFF1B0F38);
        web.addJavascriptInterface(new Bridge(), "AndroidBridge");
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if ("file".equals(u.getScheme())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
                return true;
            }
        });
        setContentView(web);
        web.loadUrl("file:///android_asset/index.html");

        tts = new TextToSpeech(this, this);
    }

    @Override
    public void onInit(int status) {
        if (status != TextToSpeech.SUCCESS) return;
        int r = tts.setLanguage(Locale.US);
        if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) tts.setLanguage(Locale.getDefault());
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { event(id, "start"); }
            @Override public void onDone(String id) { event(id, "end"); }
            @Override @Deprecated public void onError(String id) { event(id, "error"); }
            @Override public void onError(String id, int code) { event(id, "error"); }
            @Override public void onStop(String id, boolean interrupted) { event(id, "stop"); }
        });
        ttsReady = true;
        js("window.__ttsReady && window.__ttsReady()");
    }

    private void event(String id, String ev) {
        if (id == null || !id.matches("[A-Za-z0-9_-]+")) return;
        js("window.__ttsEvent && window.__ttsEvent('" + id + "','" + ev + "')");
    }

    private void js(final String code) {
        web.post(new Runnable() { @Override public void run() { web.evaluateJavascript(code, null); } });
    }

    /** Methods callable from JavaScript as window.AndroidBridge.* */
    class Bridge {
        @JavascriptInterface
        public boolean ready() { return ttsReady; }

        @JavascriptInterface
        public void speak(String text, String id, float rate, float pitch, String voiceName) {
            if (!ttsReady) { event(id, "error"); return; }
            tts.setSpeechRate(Math.max(0.5f, Math.min(2f, rate)));
            tts.setPitch(Math.max(0.5f, Math.min(2f, pitch)));
            if (voiceName != null && voiceName.length() > 0) {
                try {
                    Set<Voice> vs = tts.getVoices();
                    if (vs != null) for (Voice v : vs) if (v.getName().equals(voiceName)) { tts.setVoice(v); break; }
                } catch (Exception ignored) { }
            }
            tts.speak(text, TextToSpeech.QUEUE_ADD, null, id);
        }

        @JavascriptInterface
        public void stop() { if (tts != null) tts.stop(); }

        @JavascriptInterface
        public String voices() {
            JSONArray out = new JSONArray();
            try {
                Set<Voice> set = ttsReady ? tts.getVoices() : null;
                if (set != null) {
                    List<Voice> vs = new ArrayList<>(set);
                    Collections.sort(vs, new Comparator<Voice>() {
                        @Override public int compare(Voice a, Voice b) {
                            int n = Boolean.compare(a.isNetworkConnectionRequired(), b.isNetworkConnectionRequired());
                            return n != 0 ? n : a.getName().compareTo(b.getName());
                        }
                    });
                    for (Voice v : vs) {
                        Locale l = v.getLocale();
                        if (l == null || !"en".equals(l.getLanguage())) continue;
                        Set<String> f = v.getFeatures();
                        if (f != null && f.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)) continue;
                        JSONObject o = new JSONObject();
                        o.put("name", v.getName());
                        o.put("lang", l.toLanguageTag());
                        o.put("network", v.isNetworkConnectionRequired());
                        out.put(o);
                    }
                }
            } catch (Exception ignored) { }
            return out.toString();
        }

        @JavascriptInterface
        public void openTtsSettings() {
            runOnUiThread(new Runnable() {
                @Override public void run() {
                    try {
                        Intent i = new Intent("com.android.settings.TTS_SETTINGS");
                        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        startActivity(i);
                    } catch (Exception e) {
                        try { startActivity(new Intent(android.provider.Settings.ACTION_SETTINGS)); } catch (Exception ignored) { }
                    }
                }
            });
        }

        /** Saves a generated file (the printable card PDF) to Downloads and offers to open it. */
        @JavascriptInterface
        public String saveFile(String name, String base64, String mime) {
            try {
                byte[] data = Base64.decode(base64, Base64.DEFAULT);
                String safe = name.replaceAll("[^A-Za-z0-9._-]", "_");
                File dir = new File(getCacheDir(), "share");
                if (!dir.exists() && !dir.mkdirs()) return "error";
                FileOutputStream fo = new FileOutputStream(new File(dir, safe));
                try { fo.write(data); } finally { fo.close(); }

                boolean inDownloads = false;
                if (Build.VERSION.SDK_INT >= 29) {
                    try {
                        ContentValues cv = new ContentValues();
                        cv.put(MediaStore.MediaColumns.DISPLAY_NAME, safe);
                        cv.put(MediaStore.MediaColumns.MIME_TYPE, mime);
                        cv.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                        Uri u = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                        if (u != null) {
                            OutputStream o = getContentResolver().openOutputStream(u);
                            try { o.write(data); } finally { o.close(); }
                            inDownloads = true;
                        }
                    } catch (Exception ignored) { }
                }
                final boolean saved = inDownloads;
                final Uri shareUri = Uri.parse("content://com.jphein.lunaspellcar.files/" + safe);
                final String type = mime;
                runOnUiThread(new Runnable() {
                    @Override public void run() {
                        Toast.makeText(MainActivity.this, saved ? "Cards saved to Downloads" : "Cards ready", Toast.LENGTH_SHORT).show();
                        Intent v = new Intent(Intent.ACTION_VIEW);
                        v.setDataAndType(shareUri, type);
                        v.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        try { startActivity(Intent.createChooser(v, "Open your cards")); } catch (Exception ignored) { }
                    }
                });
                return "ok";
            } catch (Exception e) {
                return "error";
            }
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        web.evaluateJavascript("(function(){try{return window.__back?window.__back():'exit'}catch(e){return 'exit'}})()",
            new ValueCallback<String>() {
                @Override public void onReceiveValue(String v) { if (v == null || v.contains("exit")) finish(); }
            });
    }

    @Override protected void onPause() { super.onPause(); if (tts != null) tts.stop(); web.onPause(); }
    @Override protected void onResume() { super.onResume(); web.onResume(); }

    @Override
    protected void onDestroy() {
        if (tts != null) tts.shutdown();
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
