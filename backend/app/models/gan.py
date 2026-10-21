"""
Architecture GAN (cGAN conditionnel) telle que décrite au §4 du rapport
ZakhrafaAI : générateur à déconvolutions transposées conditionné par un
vecteur de bruit z + une étiquette de catégorie (Zellige / Tapis / Broderie),
et discriminateur convolutionnel binaire (LeakyReLU, sortie sigmoïde).

Ce fichier N'EST PAS chargé par défaut par l'API (voir app/services/engine.py)
car il nécessite `torch` (non installé dans cet environnement de packaging,
voir requirements-torch.txt) et des poids entraînés `gan_<pattern>_final.pth`
qui n'existent pas ici. Il est fourni pour que le projet corresponde
fidèlement à l'architecture documentée dans le rapport, et pour qu'on
puisse le brancher directement si des poids sont disponibles :

    from app.models.gan import Generator
    G = Generator(n_classes=3)
    G.load_state_dict(torch.load("gan_zellige_final.pth", map_location="cpu"))
    G.eval()

Voir app/services/engine.py::TorchGANEngine pour le point d'intégration.
"""
from __future__ import annotations

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover - torch volontairement optionnel
    TORCH_AVAILABLE = False
    nn = None  # type: ignore


if TORCH_AVAILABLE:

    class Generator(nn.Module):
        """Générateur convolutionnel conditionnel (cf. §4.1 + §4.3).

        Entrée : bruit z (dim 100) + embedding de catégorie -> déconvolutions
        transposées progressives -> Tanh en sortie (intervalle [-1, 1], §4.3).
        """

        def __init__(self, z_dim: int = 100, n_classes: int = 3, feature_maps: int = 64, img_channels: int = 3):
            super().__init__()
            self.label_emb = nn.Embedding(n_classes, z_dim)
            self.net = nn.Sequential(
                nn.ConvTranspose2d(z_dim, feature_maps * 8, 4, 1, 0, bias=False),
                nn.BatchNorm2d(feature_maps * 8),
                nn.ReLU(True),
                nn.ConvTranspose2d(feature_maps * 8, feature_maps * 4, 4, 2, 1, bias=False),
                nn.BatchNorm2d(feature_maps * 4),
                nn.ReLU(True),
                nn.ConvTranspose2d(feature_maps * 4, feature_maps * 2, 4, 2, 1, bias=False),
                nn.BatchNorm2d(feature_maps * 2),
                nn.ReLU(True),
                nn.ConvTranspose2d(feature_maps * 2, feature_maps, 4, 2, 1, bias=False),
                nn.BatchNorm2d(feature_maps),
                nn.ReLU(True),
                nn.ConvTranspose2d(feature_maps, img_channels, 4, 2, 1, bias=False),
                nn.Tanh(),  # §4.3 : sortie normalisée [-1, 1]
            )

        def forward(self, z, labels):
            z = z * self.label_emb(labels).unsqueeze(-1).unsqueeze(-1)
            return self.net(z)

    class Discriminator(nn.Module):
        """Discriminateur binaire (LeakyReLU, cf. §4.3)."""

        def __init__(self, n_classes: int = 3, feature_maps: int = 64, img_channels: int = 3):
            super().__init__()
            self.label_emb = nn.Embedding(n_classes, img_channels * 64 * 64)
            self.net = nn.Sequential(
                nn.Conv2d(img_channels, feature_maps, 4, 2, 1, bias=False),
                nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(feature_maps, feature_maps * 2, 4, 2, 1, bias=False),
                nn.BatchNorm2d(feature_maps * 2),
                nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(feature_maps * 2, feature_maps * 4, 4, 2, 1, bias=False),
                nn.BatchNorm2d(feature_maps * 4),
                nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(feature_maps * 4, 1, 4, 1, 0, bias=False),
                nn.Sigmoid(),
            )

        def forward(self, x):
            return self.net(x).view(-1)

else:

    class Generator:  # type: ignore
        def __init__(self, *a, **k):
            raise ImportError(
                "PyTorch n'est pas installé. Installez requirements-torch.txt "
                "pour utiliser l'architecture GAN réelle, ou utilisez le "
                "générateur procédural (par défaut) via app/services/engine.py."
            )

    Discriminator = Generator  # type: ignore
