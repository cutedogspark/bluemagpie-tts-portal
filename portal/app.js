const $ = (s) => document.querySelector(s);
let mode = "general";
let recordedBlob = null;
let mediaRecorder = null;

// ---------- read-aloud scripts (tone/phoneme-rich 台灣華語) ----------
const SCRIPTS = [
  "今天下班我們去逛夜市好不好？我想吃蚵仔煎、大腸包小腸，再來一杯珍珠奶茶，半糖少冰。欸對了，順便買個雞排，回家邊追劇邊吃。",
  "請你用平常聊天的語氣，自然地把這段話念完就好。不用太快，也不用太慢，輕輕鬆鬆，就像在跟朋友講話一樣。",
  "我從小在台灣長大，最喜歡這裡的人情味。巷口的早餐店老闆會記得你愛吃什麼，便利商店二十四小時都亮著燈，這種感覺真的很安心。",
  "我們來數一到十：一、二、三、四、五、六、七、八、九、十。再說幾句平常的話：早安、吃飽沒、謝謝你喔、麻煩你了、辛苦啦、改天再約。",
];
let scriptIdx = 0;
function showScript() { $("#script-text").textContent = SCRIPTS[scriptIdx % SCRIPTS.length]; }
$("#script-next").onclick = () => { scriptIdx += 1; showScript(); };
showScript();

// ---------- mode tabs ----------
document.querySelectorAll(".seg button").forEach((b) => {
  b.onclick = () => {
    mode = b.dataset.tab;
    document.querySelectorAll(".seg button").forEach((x) => x.classList.toggle("active", x === b));
    $("#panel-clone").classList.toggle("show", mode === "clone");
    $("#panel-preset").classList.toggle("show", mode === "preset");
    const cfg = mode === "clone" ? "2.8" : "2.0";
    $("#cfg").value = cfg;
    $("#cfg-val").textContent = cfg;
  };
});
$("#cfg").oninput = () => ($("#cfg-val").textContent = $("#cfg").value);
$("#steps").oninput = () => ($("#steps-val").textContent = $("#steps").value);

// clone-mode hint
$("#clone-mode").onchange = () => {
  const m = $("#clone-mode").value;
  $("#clone-mode-hint").textContent =
    m === "prompt" ? "「語音接續」會把你念的腳本當逐字稿，相似度通常最高。"
    : "「語者向量」是原本做法，只抓大概音色（較不像）。";
};

// ---------- example text (one-click fill) ----------
const EXAMPLES = [
  // 一般／實用
  "今天天氣真好，適合出門走走。",
  "歡迎來到藍鵲語音，這是台灣華語的語音合成展示。",
  "明天下午三點，我們在捷運站二號出口集合。",
  "謝謝你的幫忙，這份報告我會在週五前完成。",
  // 台灣味日常
  "真的假的？也太扯了吧！",
  "不會啦，還好啦，沒什麼。",
  "我跟你說，這間滷肉飯超好吃的！",
  "下班要不要揪一波夜市？",
  "颱風天就是要在家追劇配珍奶。",
  "好啦好啦，我知道了啦，掰掰。",
  // 長句（測試長段落的停頓與語氣）
  "感謝大家今天撥空參加這場說明會，接下來的十五分鐘，我會帶各位快速了解這個語音模型的運作方式，如果有任何問題，歡迎在最後的提問時間提出。",
  "各位旅客您好，本次列車即將進站，請站在黃線後方依序排隊；下車的旅客請先行下車，車門關閉時請勿強行進出，謝謝您的配合。",
  "今天北部地區整天多雲到陰，午後有局部短暫陣雨，外出記得攜帶雨具；中南部則是晴到多雲，紫外線偏強，請特別注意防曬與補充水分。",
  "從前從前，在一座深山裡，住著一隻羽毛湛藍的臺灣藍鵲，牠的尾巴又長又漂亮，每天清晨都會站在最高的樹梢上，向整座山谷大聲問好。",
];
const exWrap = $("#examples");
EXAMPLES.forEach((s) => {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chip";
  chip.textContent = s.length > 14 ? s.slice(0, 13) + "…" : s;
  chip.title = s;
  chip.onclick = () => { $("#text").value = s; $("#text").focus(); };
  exWrap.appendChild(chip);
});

// ---------- preset speakers ----------
fetch("/api/speakers").then((r) => r.json()).then((d) => {
  const sel = $("#speaker");
  sel.innerHTML = "";
  (d.speakers || []).forEach((s) => {
    const opt = document.createElement("option");
    opt.textContent = s;
    sel.appendChild(opt);
  });
}).catch(() => {});

// ---------- preset speaker preview ----------
const PREVIEW_LINE = "你好，這是我的聲音示範，很高興為你朗讀。";
$("#speaker-preview").onclick = async () => {
  const speaker = $("#speaker").value;
  if (!speaker) return;
  const btn = $("#speaker-preview");
  btn.disabled = true;
  $("#preview-status").textContent = `試聽 ${speaker} 中…`;
  startGpuPoll();
  try {
    const resp = await fetch("/api/tts", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: PREVIEW_LINE, cfg_value: 2.0, speaker }),
    });
    if (resp.status === 429) throw new Error("請求太頻繁，請稍候再試。");
    if (!resp.ok) throw new Error("伺服器回應 " + resp.status);
    const audio = $("#preview-audio");
    audio.src = URL.createObjectURL(await resp.blob());
    await audio.play();
    $("#preview-status").textContent = `正在播放 ${speaker} 的示範語音。`;
  } catch (e) {
    $("#preview-status").textContent = "試聽失敗：" + e.message;
  } finally {
    btn.disabled = false;
    stopGpuPoll();
  }
};

// ---------- level meter (signature element) ----------
const BAR_COUNT = 28;
const meterEl = $("#meter");
const bars = [];
for (let i = 0; i < BAR_COUNT; i++) {
  const bar = document.createElement("div");
  bar.className = "bar";
  meterEl.appendChild(bar);
  bars.push(bar);
}
let audioCtx = null, analyser = null, meterRAF = null;

function startMeter(stream) {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 64;
  audioCtx.createMediaStreamSource(stream).connect(analyser);
  const data = new Uint8Array(analyser.frequencyBinCount);
  meterEl.classList.add("live");
  const draw = () => {
    analyser.getByteFrequencyData(data);
    for (let i = 0; i < BAR_COUNT; i++) {
      const v = data[Math.floor((i / BAR_COUNT) * data.length)] / 255;
      bars[i].style.height = Math.max(8, v * 100) + "%";
    }
    meterRAF = requestAnimationFrame(draw);
  };
  draw();
}
function stopMeter() {
  if (meterRAF) cancelAnimationFrame(meterRAF);
  meterRAF = null;
  meterEl.classList.remove("live");
  bars.forEach((b) => (b.style.height = "8%"));
  if (audioCtx) { audioCtx.close().catch(() => {}); audioCtx = null; }
  analyser = null;
}

// ---------- recording ----------
let recStart = 0, timerInt = null;
function fmt(sec) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
}

$("#rec-start").onclick = async () => {
  let stream;
  try {
    // turn OFF browser processing — these alter the timbre and hurt cloning
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
  } catch (e) {
    setRecStatus("麥克風存取被拒絕，請在瀏覽器允許麥克風後重試。", "warn");
    return;
  }
  const chunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
  mediaRecorder.onstop = () => {
    recordedBlob = new Blob(chunks, { type: "audio/webm" });
    const dur = (Date.now() - recStart) / 1000;
    const pb = $("#rec-playback");
    pb.src = URL.createObjectURL(recordedBlob);
    pb.hidden = false;
    stream.getTracks().forEach((t) => t.stop());
    stopMeter();
    clearInterval(timerInt);
    if (dur < 5) {
      setRecStatus(`錄音僅 ${dur.toFixed(0)} 秒，偏短。建議念完整段腳本（8 秒以上），克隆會更準確。`, "warn");
    } else {
      setRecStatus(`已錄音 ${dur.toFixed(0)} 秒 ✓ 可直接合成，或重新錄製。`, "ok");
    }
    $("#rec-start").innerHTML = '<span class="dot"></span>重新錄音';
    $("#rec-start").classList.remove("recording");
  };

  mediaRecorder.start();
  recStart = Date.now();
  startMeter(stream);
  $("#rec-timer").textContent = "00:00";
  timerInt = setInterval(() => {
    $("#rec-timer").textContent = fmt((Date.now() - recStart) / 1000);
  }, 250);
  $("#rec-start").disabled = true;
  $("#rec-stop").disabled = false;
  $("#rec-start").classList.add("recording");
  setRecStatus("錄音中… 請照著上方腳本朗讀。", "ok");
};

$("#rec-stop").onclick = () => {
  if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  $("#rec-start").disabled = false;
  $("#rec-stop").disabled = true;
};

function setRecStatus(msg, cls) {
  const el = $("#rec-status");
  el.textContent = msg;
  el.className = "rec-status" + (cls ? " " + cls : "");
}

// ---------- live GPU monitor ----------
let gpuPoll = null;
let lastMem = null;
async function refreshGpu() {
  try {
    const d = await (await fetch("/api/gpu")).json();
    if (!d.available) {
      $("#gpu-readout").textContent = "狀態無法取得";
      $("#gpu-pct").textContent = "—";
      $("#gpu-fill").style.width = "0%";
      $("#gpu-mem-val").textContent = "—";
      $("#gpu-mem-fill").style.width = "0%";
      return;
    }
    // 使用率長條
    const util = d.util == null ? 0 : d.util;
    $("#gpu-fill").style.width = util + "%";
    $("#gpu-pct").textContent = Math.round(util) + "%";
    // 記憶體長條（以 MB 呈現；長條範圍 8192 MB）
    const MEM_MAX = 8192;
    const mb = d.mem_active_mb != null ? d.mem_active_mb
      : d.mem_self_mb != null ? d.mem_self_mb : d.mem_total_mb;
    if (mb != null) {
      $("#gpu-mem-fill").style.width = Math.min(100, (mb / MEM_MAX) * 100) + "%";
      $("#gpu-mem-val").textContent = Math.round(mb) + " MB";
      if (lastMem != null && Math.abs(mb - lastMem) >= 1) {
        const v = $("#gpu-mem-val");
        v.classList.add("bump");
        setTimeout(() => v.classList.remove("bump"), 450);
      }
      lastMem = mb;
    } else {
      $("#gpu-mem-val").textContent = "—";
    }
    // 其他讀數
    const others = [];
    if (d.power != null) others.push(d.power.toFixed(0) + " W");
    if (d.temp != null) others.push(d.temp.toFixed(0) + "°C");
    if (d.clock != null) others.push((d.clock / 1000).toFixed(2) + " GHz");
    $("#gpu-readout").textContent = others.join("　·　");
  } catch (e) { /* keep last reading */ }
}
function startGpuPoll() {
  $("#gpu").classList.add("live");
  refreshGpu();
  clearInterval(gpuPoll);
  gpuPoll = setInterval(refreshGpu, 600);
}
function stopGpuPoll() {
  clearInterval(gpuPoll);
  gpuPoll = null;
  // one last sample after the GPU settles, then drop the "live" highlight
  setTimeout(() => { refreshGpu(); $("#gpu").classList.remove("live"); }, 1500);
}
refreshGpu(); // initial idle reading on load

// ---------- synth ----------
$("#synth").onclick = async () => {
  const text = $("#text").value.trim();
  const cfg = parseFloat($("#cfg").value);
  const steps = parseInt($("#steps").value, 10);
  if (!text) return setStatus("請先輸入要合成的文字。", "error");
  if (text.length > 1000) return setStatus("文字過長，請縮短到 1000 字以內。", "error");

  if (mode === "clone") {
    if (!$("#consent").checked) return setStatus("請先勾選同意聲明，才能進行聲音克隆。", "error");
    if (!recordedBlob) return setStatus("請先錄一段參考語音。", "error");
  }

  setStatus("合成中…", "busy");
  $("#synth").disabled = true;
  startGpuPoll();
  try {
    let resp;
    if (mode === "clone") {
      const cloneMode = $("#clone-mode").value; // prompt | reference | centroid
      const fd = new FormData();
      fd.append("consent", "true");
      fd.append("text", text);
      fd.append("cfg_value", String(cfg));
      fd.append("inference_timesteps", String(steps));
      fd.append("mode", cloneMode);
      // 語音接續(prompt) 需要參考音的逐字稿 → 用上面顯示的朗讀腳本
      if (cloneMode === "prompt") fd.append("prompt_text", $("#script-text").textContent || "");
      fd.append("audio", recordedBlob, "rec.webm");
      resp = await fetch("/api/clone", { method: "POST", body: fd });
    } else {
      const body = { text, cfg_value: cfg, inference_timesteps: steps };
      if (mode === "preset") body.speaker = $("#speaker").value;
      resp = await fetch("/api/tts", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
    }
    if (resp.status === 429) throw new Error("請求太頻繁，請稍候再試。");
    if (!resp.ok) throw new Error("伺服器回應 " + resp.status);
    const blob = await resp.blob();
    const tag = mode === "clone" ? "克隆聲音"
      : mode === "preset" ? "語者 · " + $("#speaker").value
      : "文字合成";
    addClip(blob, tag, text, cfg);
    setStatus("完成 ✓", "done");
  } catch (e) {
    setStatus("合成失敗：" + e.message, "error");
  } finally {
    $("#synth").disabled = false;
    stopGpuPoll();
  }
};

function setStatus(msg, cls) {
  const el = $("#status");
  el.textContent = msg;
  el.className = "status" + (cls ? " " + cls : "");
}

// ---------- generation history (latest + comparable past clips) ----------
const MAX_CLIPS = 10;
let clips = [];
let clipSeq = 0;

function clipMeta(c) {
  const snippet = c.text.length > 18 ? c.text.slice(0, 17) + "…" : c.text;
  return `${c.tag} · 強度 ${c.cfg} · 「${snippet}」`;
}

function addClip(blob, tag, text, cfg) {
  clipSeq += 1;
  clips.unshift({ id: clipSeq, url: URL.createObjectURL(blob), tag, text, cfg });
  while (clips.length > MAX_CLIPS) URL.revokeObjectURL(clips.pop().url);
  renderClips();
}

function renderClips() {
  if (!clips.length) {
    $("#result").hidden = true;
    $("#history").hidden = true;
    return;
  }
  const latest = clips[0];
  $("#result-meta").textContent = clipMeta(latest);
  $("#out").src = latest.url;
  $("#download").href = latest.url;
  $("#download").setAttribute("download", `bluemagpie-${latest.id}.mp3`);
  $("#result").hidden = false;

  const past = clips.slice(1);
  const list = $("#history-list");
  list.innerHTML = "";
  past.forEach((c) => {
    const item = document.createElement("div");
    item.className = "clip-item";

    const meta = document.createElement("div");
    meta.className = "clip-meta";
    meta.textContent = clipMeta(c);

    const row = document.createElement("div");
    row.className = "clip-player";
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = c.url;
    const dl = document.createElement("a");
    dl.className = "ghost-btn small";
    dl.textContent = "下載";
    dl.href = c.url;
    dl.setAttribute("download", `bluemagpie-${c.id}.mp3`);
    row.appendChild(audio);
    row.appendChild(dl);

    item.appendChild(meta);
    item.appendChild(row);
    list.appendChild(item);
  });
  $("#history").hidden = past.length === 0;
}

$("#history-clear").onclick = () => {
  clips.forEach((c) => URL.revokeObjectURL(c.url));
  clips = [];
  renderClips();
  setStatus("已清除產生紀錄。", "");
};
