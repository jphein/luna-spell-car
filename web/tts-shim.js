/* Android WebView has no speechSynthesis. This shim maps the Web Speech API
   onto the native TextToSpeech engine exposed by MainActivity as AndroidBridge. */
(function () {
  var B = window.AndroidBridge;
  if (!B) return;
  var pending = {}, n = 0, voices = [];
  function loadVoices() {
    try {
      voices = JSON.parse(B.voices()).map(function (v, i) {
        var region = (v.lang.split("-")[1] || "").toUpperCase();
        return { name: v.name, lang: v.lang, voiceURI: v.name, localService: !v.network, default: false,
                 label: "Voice " + (i + 1) + (region ? " (" + region + ")" : "") + (v.network ? " · needs internet" : "") };
      });
    } catch (e) { voices = []; }
  }
  window.__ttsEvent = function (id, ev) {
    var u = pending[id]; if (!u) return;
    if (ev === "start") { if (u.onstart) u.onstart({}); return; }
    delete pending[id];
    if (ev === "stop") return;
    var f = ev === "error" ? (u.onerror || u.onend) : u.onend;
    if (f) f({});
  };
  window.__ttsReady = function () { loadVoices(); if (synth.onvoiceschanged) synth.onvoiceschanged(); };
  function Utterance(text) { this.text = text || ""; this.rate = 1; this.pitch = 1; this.volume = 1; this.voice = null; this.lang = "en-US";
    this.onstart = null; this.onend = null; this.onerror = null; }
  var synth = {
    speaking: false, pending: false, paused: false, onvoiceschanged: null,
    speak: function (u) { var id = "u" + (++n); pending[id] = u;
      B.speak(String(u.text), id, Number(u.rate) || 1, Number(u.pitch) || 1, u.voice ? u.voice.name : ""); },
    cancel: function () { pending = {}; B.stop(); },
    getVoices: function () { if (!voices.length && B.ready()) loadVoices(); return voices; },
    pause: function () {}, resume: function () {}
  };
  try { Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true }); } catch (e) { window.speechSynthesis = synth; }
  window.SpeechSynthesisUtterance = Utterance;
})();
