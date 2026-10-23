"""Tests de l'architecture GAN et du branchement de poids (ignorés sans torch)."""
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from app.models.gan import Discriminator, Generator  # noqa: E402
from app.services import engine  # noqa: E402


def test_generator_outputs_64x64():
    z = torch.randn(4, 100, 1, 1)
    labels = torch.tensor([0, 1, 2, 0])
    assert Generator().eval()(z, labels).shape == (4, 3, 64, 64)


def test_discriminator_one_score_per_image():
    x = torch.randn(4, 3, 64, 64)
    labels = torch.tensor([0, 1, 2, 0])
    scores = Discriminator()(x, labels)
    assert scores.shape == (4,)
    assert bool(((scores >= 0) & (scores <= 1)).all())


def test_discriminator_uses_label():
    d = Discriminator().eval()
    x = torch.randn(1, 3, 64, 64)
    assert not torch.equal(d(x, torch.tensor([0])), d(x, torch.tensor([1])))


def test_trained_weights_are_cached_and_upsampled(tmp_path, monkeypatch):
    torch.save(Generator().state_dict(), tmp_path / "gan_zellige_final.pth")
    monkeypatch.setattr(engine, "WEIGHTS_DIR", tmp_path)
    engine._load_torch_gan.cache_clear()
    try:
        first = engine.generate("zellige", "gan", seed=3)
        second = engine.generate("zellige", "gan", seed=3)
        assert first.source == "trained_weights"
        assert first.image.size == (256, 256)
        assert first.image.tobytes() == second.image.tobytes()
        assert engine._load_torch_gan.cache_info().misses == 1
    finally:
        engine._load_torch_gan.cache_clear()


def test_corrupt_weights_fall_back_and_log(tmp_path, monkeypatch, caplog):
    (tmp_path / "gan_tapis_final.pth").write_bytes(b"pas des poids")
    monkeypatch.setattr(engine, "WEIGHTS_DIR", tmp_path)
    engine._load_torch_gan.cache_clear()
    result = engine.generate("tapis", "gan", seed=3)
    assert result.source == "procedural"
    assert any("repli" in r.getMessage() for r in caplog.records)
