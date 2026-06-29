import soundfile as sf

from app.model_service import build_model_service

svc = build_model_service()
print("speakers:", svc.list_speakers())
print("sample_rate:", svc.sample_rate)

# 1) general synthesis
samples = svc.synthesize("今天天氣真好，適合出門散步。", cfg_value=2.0)
print("general samples:", samples.shape, samples.dtype)
sf.write("/tmp/bluemagpie_smoke.wav", samples, svc.sample_rate)
print("wrote /tmp/bluemagpie_smoke.wav")

# 2) preset speaker (if any presets loaded)
speakers = svc.list_speakers()
if speakers:
    s0 = speakers[0]
    ps = svc.synthesize("這是預設語者測試。", cfg_value=2.0, speaker=s0)
    sf.write(f"/tmp/bluemagpie_preset_{s0}.wav", ps, svc.sample_rate)
    print(f"preset {s0} samples:", ps.shape, "-> /tmp/bluemagpie_preset_{}.wav".format(s0))

# 3) clone path: extract a centroid from the general wav, then synth with it
centroid = svc.extract_centroid("/tmp/bluemagpie_smoke.wav")
try:
    shape = centroid.shape
except AttributeError:
    shape = type(centroid)
print("centroid:", shape)
cl = svc.synthesize_with_centroid("這是用我的聲音克隆出來的句子。", centroid, cfg_value=2.8)
sf.write("/tmp/bluemagpie_clone.wav", cl, svc.sample_rate)
print("clone samples:", cl.shape, "-> /tmp/bluemagpie_clone.wav")
print("SMOKE OK")
