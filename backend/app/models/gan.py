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

Résolution : le générateur produit des images **64x64** (bruit 1x1 ->
4 -> 8 -> 16 -> 32 -> 64). L'architecture n'est pas modifiée pour rester
compatible avec les poids `.pth` déjà entraînés ; c'est le moteur
(app/services/engine.py::_generate_with_torch_gan) qui agrandit la sortie
à la taille demandée (256x256 par défaut en mode « gan »).

Voir app/services/engine.py::_generate_with_torch_gan pour le point
d'intégration.
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
        Sortie : (B, 3, 64, 64).
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
        """Discriminateur binaire conditionnel (LeakyReLU, cf. §4.3).

        Entrée : image (B, 3, 64, 64) + étiquette de catégorie. L'étiquette
        est projetée en une carte 64x64 concaténée comme 4e canal (cGAN), puis
        quatre convolutions stride 2 (64 -> 32 -> 16 -> 8 -> 4) et une
        convolution 4x4 finale donnent **un score par image** : sortie (B,).
        """

        def __init__(self, n_classes: int = 3, feature_maps: int = 64, img_channels: int = 3, img_size: int = 64):
            super().__init__()
            self.img_size = img_size
            self.label_emb = nn.Embedding(n_classes, img_size * img_size)
            self.net = nn.Sequential(
                nn.Conv2d(img_channels + 1, feature_maps, 4, 2, 1, bias=False),  # 64 -> 32
                nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(feature_maps, feature_maps * 2, 4, 2, 1, bias=False),  # 32 -> 16
                nn.BatchNorm2d(feature_maps * 2),
                nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(feature_maps * 2, feature_maps * 4, 4, 2, 1, bias=False),  # 16 -> 8
                nn.BatchNorm2d(feature_maps * 4),
                nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(feature_maps * 4, feature_maps * 8, 4, 2, 1, bias=False),  # 8 -> 4
                nn.BatchNorm2d(feature_maps * 8),
                nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(feature_maps * 8, 1, 4, 1, 0, bias=False),  # 4 -> 1
                nn.Sigmoid(),
            )

        def forward(self, x, labels):
            label_map = self.label_emb(labels).view(-1, 1, self.img_size, self.img_size)
            return self.net(torch.cat([x, label_map], dim=1)).view(-1)

else:

    class Generator:  # type: ignore
        def __init__(self, *a, **k):
            raise ImportError(
                "PyTorch n'est pas installé. Installez requirements-torch.txt "
                "pour utiliser l'architecture GAN réelle, ou utilisez le "
                "générateur procédural (par défaut) via app/services/engine.py."
            )

    Discriminator = Generator  # type: ignore
