"""
Menu de sélection de musique pour Xylophone Champion.

Affiche la liste des fichiers MP3 présents dans le dossier music/ et permet
d'en choisir un avant de lancer la partie.

Auteurs: Julien Behani, Enzo Fournier - 2026
"""

import os
import sys
import pygame
import constants as const

MUSIC_DIR = "music"

# Nombre maximum d'entrées affichées simultanément
_MAX_VISIBLE = 9

# Couleurs thème xylophone
_COLOR_BG        = (10,  10,  25)
_COLOR_TITLE     = (255, 220,  50)
_COLOR_SUBTITLE  = (160, 160, 160)
_COLOR_ITEM      = (200, 200, 200)
_COLOR_SELECTED  = (255, 220,  50)
_COLOR_BORDER    = (255, 220,  50)
_COLOR_HINT      = (100, 100, 100)
_COLOR_ERROR     = (200,  80,  80)


class MenuScene:
    """
    Scène du menu principal : sélection d'une musique.

    Retourne un dict d'action via handle_event() :
    - {'action': 'play', 'music_path': str} quand le joueur valide.
    """

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.width, self.height = screen.get_size()

        self._fonts = {
            'title':    pygame.font.Font(None, 90),
            'subtitle': pygame.font.Font(None, 42),
            'item':     pygame.font.Font(None, 52),
            'small':    pygame.font.Font(None, 32),
        }

        self._music_files = self._scan_music()
        self._selected    = 0
        self._scroll      = 0
        self._tick        = 0

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _scan_music(self) -> list[dict]:
        """
        Recherche les fichiers MP3 dans le dossier music/.

        Returns:
            Liste de dicts {'name': str, 'path': str} triée alphabétiquement.
        """
        if not os.path.exists(MUSIC_DIR):
            os.makedirs(MUSIC_DIR, exist_ok=True)
        files = []
        for filename in sorted(os.listdir(MUSIC_DIR), key=str.lower):
            if filename.lower().endswith('.mp3'):
                files.append({
                    'name': os.path.splitext(filename)[0],
                    'path': os.path.join(MUSIC_DIR, filename),
                })
        return files

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> dict | None:
        """
        Traite un événement pygame.

        Args:
            event: Événement pygame à traiter.

        Returns:
            Dict d'action ou None.
        """
        if event.type != pygame.KEYDOWN:
            return None

        if event.key == pygame.K_UP:
            self._selected = max(0, self._selected - 1)
            self._update_scroll()

        elif event.key == pygame.K_DOWN:
            self._selected = min(len(self._music_files) - 1, self._selected + 1)
            self._update_scroll()

        elif event.key == const.KEY_ACCEPT:
            if self._music_files:
                return {
                    'action':     'play',
                    'music_path': self._music_files[self._selected]['path'],
                }

        elif event.key == const.KEY_REFUSE:
            pygame.quit()
            sys.exit()

        return None

    def update(self):
        """Met à jour les animations du menu."""
        self._tick += 1

    def draw(self):
        """Dessine le menu complet."""
        self.screen.fill(_COLOR_BG)
        self._draw_title()
        if self._music_files:
            self._draw_list()
        else:
            self._draw_empty()
        self._draw_hint()

    # ------------------------------------------------------------------
    # Dessin
    # ------------------------------------------------------------------

    def _draw_title(self):
        """Affiche le titre et le sous-titre."""
        title = self._fonts['title'].render("XYLOPHONE CHAMPION", True, _COLOR_TITLE)
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 55))

        sub = self._fonts['subtitle'].render("Sélectionnez une musique", True, _COLOR_SUBTITLE)
        self.screen.blit(sub, (self.width // 2 - sub.get_width() // 2, 160))

    def _draw_list(self):
        """Affiche la liste des musiques disponibles."""
        item_h  = 68
        start_y = 220
        box_w   = 820

        visible = self._music_files[self._scroll:self._scroll + _MAX_VISIBLE]

        for idx, music in enumerate(visible):
            real_idx   = idx + self._scroll
            is_selected = real_idx == self._selected
            y = start_y + idx * item_h

            box_x = self.width // 2 - box_w // 2
            box_rect = pygame.Rect(box_x, y, box_w, item_h - 6)

            if is_selected:
                pygame.draw.rect(self.screen, (35, 35, 70), box_rect, border_radius=10)
                pygame.draw.rect(self.screen, _COLOR_BORDER, box_rect, 2, border_radius=10)
                color  = _COLOR_SELECTED
                prefix = "▶  "
            else:
                color  = _COLOR_ITEM
                prefix = "    "

            max_text_w = box_w - 36
            name = music['name']
            text = self._fonts['item'].render(prefix + name, True, color)
            if text.get_width() > max_text_w:
                while name and self._fonts['item'].render(prefix + name + "...", True, color).get_width() > max_text_w:
                    name = name[:-1]
                text = self._fonts['item'].render(prefix + name + "...", True, color)
            self.screen.blit(text, (box_x + 18, y + (item_h - 6 - text.get_height()) // 2))

    def _draw_empty(self):
        """Affiche un message si aucun MP3 n'est trouvé."""
        msg = self._fonts['item'].render(
            "Aucun fichier MP3 trouvé dans music/", True, _COLOR_ERROR
        )
        hint = self._fonts['small'].render(
            "Ajoutez des fichiers .mp3 dans le dossier music/ puis relancez le jeu.",
            True, _COLOR_SUBTITLE,
        )
        cy = self.height // 2 - 40
        self.screen.blit(msg,  (self.width // 2 - msg.get_width()  // 2, cy))
        self.screen.blit(hint, (self.width // 2 - hint.get_width() // 2, cy + 65))

    def _draw_hint(self):
        """Affiche les contrôles en bas de l'écran."""
        hint = self._fonts['small'].render(
            "↑ ↓  Naviguer     ENTRÉE  Jouer     ÉCHAP  Quitter",
            True, _COLOR_HINT,
        )
        self.screen.blit(hint, (self.width // 2 - hint.get_width() // 2, self.height - 48))

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _update_scroll(self):
        """Ajuste le décalage de scroll pour garder la sélection visible."""
        if self._selected < self._scroll:
            self._scroll = self._selected
        elif self._selected >= self._scroll + _MAX_VISIBLE:
            self._scroll = self._selected - _MAX_VISIBLE + 1
