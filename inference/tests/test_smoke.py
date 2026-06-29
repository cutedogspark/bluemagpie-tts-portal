from app.fake_model_service import FakeModelService


def test_fake_service_speakers():
    svc = FakeModelService()
    assert svc.list_speakers() == ["hung_yi_lee", "female_voice"]
    assert svc.sample_rate == 48000
