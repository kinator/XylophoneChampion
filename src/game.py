"""
Scène de jeu principale pour Xylophone Champion.

Gère la boucle de jeu, l'affichage des notes tombantes,
la détection des frappes et le calcul du score.

Auteurs: Julien Behani, Enzo Fournier - 2026
"""

import os
import random
import pygame
import constants

from note import (
    Note,
    NUM_LANES,
    LANE_COLORS,
    LANE_KEYS_DISPLAY,
    POOR_WINDOW,
    JUDGMENT_POINTS,
    FALL_SPEED,
    HIT_Y,
    NOTE_HEIGHT,
    DIRECTIONS,
    DIRECTION_ARROWS,
)
from analyzer import analyze_music
from constants import KEY_ACCEPT

# ------------------------------------------------------------------
# Constantes de mise en page
# ------------------------------------------------------------------

_SCREEN_W    = 1280
_SCREEN_H    = 1024

_LANE_W      = 132          # largeur d'une piste (pixels)
_LANE_GAP    = 18           # espace entre deux pistes (pixels)
_LANE_AREA_W = NUM_LANES * _LANE_W + (NUM_LANES - 1) * _LANE_GAP
_LANE_LEFT   = (_SCREEN_W - _LANE_AREA_W) // 2   # 271 px

_LANE_TOP    = 90           # y du haut de la zone de jeu
_HIT_ZONE_H  = 38           # hauteur de la zone de frappe (pixels)

# Durée du compte à rebours avant le début de la musique (secondes)
_COUNTDOWN   = 3.0

# Fenêtre de temps visible (secondes) : les notes apparaissent en haut
# quand il reste TIME_VISIBLE secondes avant leur heure de frappe.
_TIME_VISIBLE = HIT_Y / FALL_SPEED   # ≈ 2.07 s

# Touches par défaut (mode normal) : R T Y H
_LANE_KEYS = [pygame.K_r, pygame.K_t, pygame.K_y, pygame.K_h]

# Mode difficile : R T Y pour les pistes 1-2-3, flèches pour la piste 0
_HARD_LANE_KEYS = [pygame.K_r, pygame.K_t, pygame.K_y]   # → pistes 1, 2, 3
_ARROW_KEYS = {
    pygame.K_UP:    'up',
    pygame.K_DOWN:  'down',
    pygame.K_LEFT:  'left',
    pygame.K_RIGHT: 'right',
}

# Couleurs des flèches directionnelles (mode difficile, piste 0)
_ARROW_COLORS = {
    'up':    ( 60, 230,  80),   # vert
    'down':  (255, 220,  50),   # jaune
    'left':  ( 80, 160, 255),   # bleu
    'right': (255,  80, 200),   # magenta
}

# ------------------------------------------------------------------
# Couleurs
# ------------------------------------------------------------------

_COL_BG          = (10,  10,  25)
_COL_LANE_BG     = lambda c: tuple(max(0, v - 170) for v in c)   # noqa: E731
_COL_WHITE       = (255, 255, 255)
_COL_GRAY        = (130, 130, 130)
_COL_HEALTH_HI   = ( 60, 200,  80)
_COL_HEALTH_MID  = (220, 180,  50)
_COL_HEALTH_LO   = (200,  50,  50)
_COL_PERFECT     = (255, 220,  50)
_COL_GOOD        = (100, 200, 255)
_COL_MISS        = (200,  50,  50)
_COL_OVERLAY     = (  0,   0,   0, 160)


class GameScene:
    """
    Scène de jeu Guitar-Hero-like.

    États internes (self._state) :
    - 'loading'   : analyse du fichier audio en cours
    - 'countdown' : compte à rebours avant la musique
    - 'playing'   : jeu en cours
    - 'paused'    : jeu en pause
    - 'result'    : écran de résultat final
    - 'error'     : erreur de chargement
    """

    def __init__(self, screen: pygame.Surface, music_path: str, difficulty: str = 'normal'):
        self.screen     = screen
        self.width      = screen.get_width()
        self.height     = screen.get_height()
        self.music_path = music_path
        self.music_name = os.path.splitext(os.path.basename(music_path))[0]
        self._difficulty = difficulty

        self._fonts = {
            'score':    pygame.font.Font(None, 64),
            'combo':    pygame.font.Font(None, 52),
            'judgment': pygame.font.Font(None, 62),
            'info':     pygame.font.Font(None, 36),
            'big':      pygame.font.Font(None, 210),
            'loading':  pygame.font.Font(None, 56),
            'result':   pygame.font.Font(None, 100),
        }

        # --- Notes ---
        self._notes: list[Note] = []
        self._active: list[Note] = []   # notes dans la fenêtre de jeu
        self._note_idx = 0              # prochain index à injecter

        # --- Score ---
        self.score         = 0
        self.combo         = 0
        self.max_combo     = 0
        self.perfect_count = 0
        self.good_count    = 0
        self.miss_count    = 0
        self.health        = 100.0      # 0-100

        # --- Timing ---
        self._music_duration  = 0.0
        self._music_start_ms  = 0       # ticks pygame au moment du play()
        self._paused_at_ms    = 0
        self._current_time    = 0.0

        # --- Visuels ---
        self._key_pressed  = [False] * NUM_LANES
        self._key_flash    = [0] * NUM_LANES    # frames restantes de flash
        self._judgments: list[dict] = []        # textes animés

        # --- État ---
        self._state         = 'loading'
        self._load_done     = False
        self._countdown_ms  = 0
        self._error_msg     = ""

    # ==================================================================
    # Boucle principale
    # ==================================================================

    def handle_event(self, event: pygame.event.Event) -> dict | None:
        """
        Traite un événement pygame.

        Args:
            event: Événement reçu depuis la boucle principale.

        Returns:
            Dict d'action ({'action': 'menu'}) ou None.
        """
        if event.type == pygame.KEYDOWN:
            # Retour menu
            if event.key == constants.KEY_MENU:
                pygame.mixer.music.stop()
                return {'action': 'menu'}

            # Pause / reprise
            if event.key == constants.KEY_PAUSE:
                if self._state == 'playing':
                    self._pause()
                elif self._state == 'paused':
                    self._resume()

            # Frappe de piste
            if self._state == 'playing':
                if self._difficulty == 'hard':
                    if event.key in _ARROW_KEYS:
                        self._key_pressed[0] = True
                        self._key_flash[0]   = 12
                        self._press_lane_arrow(_ARROW_KEYS[event.key])
                    else:
                        for i, key in enumerate(_HARD_LANE_KEYS):
                            if event.key == key:
                                self._press_lane(i + 1)
                else:
                    for i, key in enumerate(_LANE_KEYS):
                        if event.key == key:
                            self._press_lane(i)

            # Écran de résultat → menu
            if self._state == 'result' and event.key == KEY_ACCEPT:
                return {'action': 'menu'}

        if event.type == pygame.KEYUP:
            if self._difficulty == 'hard':
                if event.key in _ARROW_KEYS:
                    self._key_pressed[0] = False
                else:
                    for i, key in enumerate(_HARD_LANE_KEYS):
                        if event.key == key:
                            self._key_pressed[i + 1] = False
            else:
                for i, key in enumerate(_LANE_KEYS):
                    if event.key == key:
                        self._key_pressed[i] = False

        return None

    def update(self):
        """Met à jour l'état du jeu pour le frame courant."""
        if self._state == 'loading':
            if not self._load_done:
                # Laisser draw() afficher l'écran de chargement d'abord
                self._load_done = True
            else:
                self._load()
            return

        if self._state == 'countdown':
            elapsed_ms = pygame.time.get_ticks() - self._countdown_ms
            if elapsed_ms >= _COUNTDOWN * 1000:
                self._start_music()
            return

        if self._state != 'playing':
            return

        ct = self._get_time()
        self._current_time = ct

        # Injecter les notes qui entrent dans la fenêtre visible
        while self._note_idx < len(self._notes):
            nxt = self._notes[self._note_idx]
            if nxt.time <= ct + _TIME_VISIBLE + 0.5:
                self._active.append(nxt)
                self._note_idx += 1
            else:
                break

        # Détecter les notes ratées
        for note in self._active:
            if note.is_active() and note.check_missed(ct):
                self._register_miss(note)

        # Nettoyer les notes traitées et sorties de l'écran
        self._active = [
            n for n in self._active
            if not (
                (n.hit     and ct - n.time > 0.4) or
                (n.missed  and ct - n.time > 0.6)
            )
        ]

        # Mettre à jour les flashs de touches
        self._key_flash = [max(0, f - 1) for f in self._key_flash]

        # Mettre à jour les textes de jugement (remontée + fondu)
        self._judgments = [
            {**j, 'y': j['y'] - 2, 'alpha': max(0, j['alpha'] - 9)}
            for j in self._judgments
            if j['alpha'] > 0
        ]

        # Fin de partie : musique terminée ET toutes les notes traitées
        if ct > self._music_duration + 1.5 and self._note_idx >= len(self._notes):
            self._end()

        # Vie à zéro
        if self.health <= 0:
            self._end()

    def draw(self):
        """Dessine la frame courante."""
        self.screen.fill(_COL_BG)

        if self._state == 'loading':
            self._draw_loading("Analyse de la musique en cours...")
            return

        if self._state == 'error':
            self._draw_loading(f"Erreur : {self._error_msg}")
            return

        if self._state == 'countdown':
            self._draw_countdown()
            return

        # Jeu en cours (playing / paused / result)
        self._draw_side_stats()
        self._draw_lanes()
        self._draw_notes()
        self._draw_hit_zones()
        self._draw_key_labels()
        self._draw_judgments()
        self._draw_hud()

        if self._state == 'paused':
            self._draw_pause_overlay()

        if self._state == 'result':
            self._draw_result()

    # ==================================================================
    # Chargement
    # ==================================================================

    def _load(self):
        """Lance l'analyse audio et prépare le countdown."""
        try:
            raw_notes, _tempo, self._music_duration = analyze_music(self.music_path)
            self._notes = [Note(n['lane'], n['time']) for n in raw_notes]
            if self._difficulty == 'hard':
                for note in self._notes:
                    if note.lane == 0:
                        note.direction = random.choice(DIRECTIONS)
            pygame.mixer.music.load(self.music_path)
            self._state        = 'countdown'
            self._countdown_ms = pygame.time.get_ticks()
        except Exception as exc:  # pylint: disable=broad-except
            self._error_msg = str(exc)[:80]
            self._state = 'error'

    def _start_music(self):
        """Lance la lecture de la musique et démarre le chrono."""
        pygame.mixer.music.play()
        self._music_start_ms = pygame.time.get_ticks()
        self._state = 'playing'

    # ==================================================================
    # Timing
    # ==================================================================

    def _get_time(self) -> float:
        """
        Retourne le temps écoulé depuis le début de la musique (secondes).

        Returns:
            Temps en secondes, peut être négatif pendant le countdown.
        """
        return (pygame.time.get_ticks() - self._music_start_ms) / 1000.0

    # ==================================================================
    # Pause
    # ==================================================================

    def _pause(self):
        """Met le jeu en pause."""
        self._state       = 'paused'
        self._paused_at_ms = pygame.time.get_ticks()
        pygame.mixer.music.pause()

    def _resume(self):
        """Reprend le jeu après une pause."""
        paused_duration      = pygame.time.get_ticks() - self._paused_at_ms
        self._music_start_ms += paused_duration
        self._state           = 'playing'
        pygame.mixer.music.unpause()

    # ==================================================================
    # Frappe
    # ==================================================================

    def _press_lane(self, lane: int):
        """
        Traite l'appui sur une piste.

        Recherche la note active la plus proche dans la piste et tente de la frapper.

        Args:
            lane: Indice de la piste frappée (0-4).
        """
        self._key_pressed[lane] = True
        self._key_flash[lane]   = 12

        ct         = self._current_time
        best_note  = None
        best_diff  = float('inf')

        for note in self._active:
            if note.lane == lane and note.is_active():
                diff = abs(ct - note.time)
                if diff <= POOR_WINDOW and diff < best_diff:
                    best_diff = diff
                    best_note = note

        if best_note:
            judgment = best_note.try_hit(ct)
            if judgment:
                self._register_hit(judgment, lane)

    def _press_lane_arrow(self, direction: str):
        """
        Mode difficile — traite une touche directionnelle pour la piste 0.

        Cherche la note active de piste 0 dont la direction correspond.

        Args:
            direction: Direction pressée ('up', 'down', 'left', 'right').
        """
        ct        = self._current_time
        best_note = None
        best_diff = float('inf')

        for note in self._active:
            if note.lane == 0 and note.is_active() and note.direction == direction:
                diff = abs(ct - note.time)
                if diff <= POOR_WINDOW and diff < best_diff:
                    best_diff = diff
                    best_note = note

        if best_note:
            judgment = best_note.try_hit(ct)
            if judgment:
                self._register_hit(judgment, 0)

    def _register_hit(self, judgment: str, lane: int):
        """
        Enregistre un coup réussi et met à jour score / combo.

        Args:
            judgment: 'perfect' ou 'good'.
            lane: Piste concernée.
        """
        self.combo     += 1
        self.max_combo  = max(self.max_combo, self.combo)
        multiplier      = min(4, 1 + self.combo // 10)

        self.score += JUDGMENT_POINTS[judgment] * multiplier

        if judgment == 'perfect':
            self.perfect_count += 1
            color = _COL_PERFECT
        else:
            self.good_count += 1
            color = _COL_GOOD

        self._spawn_judgment(judgment.upper(), lane, color)

    def _register_miss(self, note: Note):
        """
        Enregistre un raté et pénalise la vie / le combo.

        Args:
            note: La note ratée.
        """
        self.miss_count += 1
        self.combo       = 0
        self.health      = max(0.0, self.health - 10.0)
        self._spawn_judgment("MISS", note.lane, _COL_MISS)

    def _spawn_judgment(self, text: str, lane: int, color: tuple):
        """
        Crée un texte de jugement animé centré sur la piste.

        Args:
            text: Texte à afficher ('PERFECT', 'GOOD', 'MISS').
            lane: Piste sur laquelle afficher le texte.
            color: Couleur RGB du texte.
        """
        x = _LANE_LEFT + lane * (_LANE_W + _LANE_GAP) + _LANE_W // 2
        self._judgments.append({
            'text':  text,
            'x':     x,
            'y':     HIT_Y - 90,
            'alpha': 255,
            'color': color,
        })

    # ==================================================================
    # Fin de partie
    # ==================================================================

    def _end(self):
        """Termine la partie et passe à l'écran de résultat."""
        self._state = 'result'
        pygame.mixer.music.stop()

    # ==================================================================
    # Dessin
    # ==================================================================

    def _draw_loading(self, message: str):
        """Affiche l'écran de chargement avec un message."""
        text = self._fonts['loading'].render(message, True, (255, 220, 50))
        self.screen.blit(text, (self.width // 2 - text.get_width() // 2, self.height // 2 - 35))
        sub = self._fonts['info'].render(self.music_name, True, (160, 160, 160))
        self.screen.blit(sub, (self.width // 2 - sub.get_width() // 2, self.height // 2 + 30))

    def _draw_countdown(self):
        """Affiche le compte à rebours (3, 2, 1…)."""
        elapsed  = (pygame.time.get_ticks() - self._countdown_ms) / 1000.0
        remaining = _COUNTDOWN - elapsed

        # Nom de la musique
        name = self._fonts['combo'].render(self.music_name, True, (160, 160, 160))
        self.screen.blit(name, (self.width // 2 - name.get_width() // 2, 180))

        # Chiffre du compte à rebours
        n = max(1, int(remaining) + 1)
        countdown_colors = {3: (200, 80, 80), 2: (220, 180, 50), 1: (80, 200, 80)}
        color = countdown_colors.get(n, _COL_WHITE)
        num = self._fonts['big'].render(str(n), True, color)
        self.screen.blit(num, (self.width // 2 - num.get_width() // 2, self.height // 2 - 120))

    def _draw_lanes(self):
        """Dessine les bandes colorées de chaque piste."""
        for i in range(NUM_LANES):
            col  = LANE_COLORS[i]
            bg   = _COL_LANE_BG(col)
            x    = _LANE_LEFT + i * (_LANE_W + _LANE_GAP)
            h    = HIT_Y - _LANE_TOP + _HIT_ZONE_H

            # Fond sombre de la piste
            pygame.draw.rect(self.screen, bg, (x, _LANE_TOP, _LANE_W, h))
            # Bordure colorée
            pygame.draw.rect(self.screen, col, (x, _LANE_TOP, _LANE_W, h), 2)

    def _draw_notes(self):
        """Dessine les notes tombantes dans leurs pistes respectives."""
        ct = self._current_time
        for note in self._active:
            if not note.is_active():
                continue

            y = note.get_y(ct)
            if y < _LANE_TOP - NOTE_HEIGHT or y > HIT_Y + NOTE_HEIGHT:
                continue

            col = LANE_COLORS[note.lane]
            x   = _LANE_LEFT + note.lane * (_LANE_W + _LANE_GAP)

            # Corps de la note
            rect = pygame.Rect(x + 6, y - NOTE_HEIGHT // 2, _LANE_W - 12, NOTE_HEIGHT)
            pygame.draw.rect(self.screen, col, rect, border_radius=7)

            # Surbrillance en haut de la note
            hl_color = tuple(min(255, c + 80) for c in col)
            hl_rect  = pygame.Rect(x + 6, y - NOTE_HEIGHT // 2, _LANE_W - 12, 7)
            pygame.draw.rect(self.screen, hl_color, hl_rect, border_radius=7)

            # Flèche directionnelle (mode difficile, piste 0)
            if self._difficulty == 'hard' and note.lane == 0 and note.direction:
                self._draw_direction_arrow(x, y, note.direction)

    def _draw_direction_arrow(self, note_x: int, note_y: int, direction: str):
        """
        Dessine une grande flèche colorée (par direction) sur une note de piste 0.

        Args:
            note_x: X de gauche de la piste.
            note_y: Y central de la note.
            direction: 'up', 'down', 'left' ou 'right'.
        """
        cx    = note_x + _LANE_W // 2
        cy    = note_y
        v     = NOTE_HEIGHT // 2 - 1   # demi-hauteur (quasi toute la note)
        hw    = 22                      # demi-largeur de la base

        if direction == 'up':
            pts = [(cx, cy - v), (cx - hw, cy + v), (cx + hw, cy + v)]
        elif direction == 'down':
            pts = [(cx, cy + v), (cx - hw, cy - v), (cx + hw, cy - v)]
        elif direction == 'left':
            pts = [(cx - hw, cy), (cx + v, cy - v), (cx + v, cy + v)]
        elif direction == 'right':
            pts = [(cx + hw, cy), (cx - v, cy - v), (cx - v, cy + v)]
        else:
            return

        color      = _ARROW_COLORS[direction]
        shadow_pts = [(x + 2, y + 2) for x, y in pts]
        pygame.draw.polygon(self.screen, (0, 0, 0), shadow_pts)   # ombre décalée
        pygame.draw.polygon(self.screen, color,     pts)           # remplissage coloré
        pygame.draw.polygon(self.screen, (0, 0, 0), pts, 2)       # contour net

    def _draw_hit_zones(self):
        """Dessine les zones de frappe en bas de chaque piste."""
        for i in range(NUM_LANES):
            col  = LANE_COLORS[i]
            x    = _LANE_LEFT + i * (_LANE_W + _LANE_GAP)
            rect = pygame.Rect(x, HIT_Y - _HIT_ZONE_H // 2, _LANE_W, _HIT_ZONE_H)

            if self._key_pressed[i] or self._key_flash[i] > 0:
                # Piste allumée lors d'un appui
                bright = tuple(min(255, c + 60) for c in col)
                pygame.draw.rect(self.screen, bright, rect, border_radius=9)

                # Halo semi-transparent
                glow = pygame.Surface((_LANE_W + 24, _HIT_ZONE_H + 40), pygame.SRCALPHA)
                glow.fill((*col, 55))
                self.screen.blit(glow, (x - 12, HIT_Y - _HIT_ZONE_H // 2 - 20))
            else:
                pygame.draw.rect(self.screen, col, rect, border_radius=9)

            # Ligne de référence
            pygame.draw.line(
                self.screen, _COL_WHITE,
                (x, HIT_Y), (x + _LANE_W, HIT_Y), 2
            )

    def _draw_key_labels(self):
        """Affiche les labels des touches sous les zones de frappe."""
        if self._difficulty == 'hard':
            labels = ['←↑↓→', 'R', 'T', 'Y']
        else:
            labels = LANE_KEYS_DISPLAY
        for i, label in enumerate(labels):
            x   = _LANE_LEFT + i * (_LANE_W + _LANE_GAP) + _LANE_W // 2
            col = _COL_WHITE if self._key_pressed[i] else LANE_COLORS[i]
            txt = self._fonts['info'].render(label, True, col)
            self.screen.blit(txt, (x - txt.get_width() // 2, HIT_Y + _HIT_ZONE_H // 2 + 8))

    def _draw_judgments(self):
        """Affiche les textes de jugement animés (remontée + fondu)."""
        font = self._fonts['judgment']
        for j in self._judgments:
            if j['alpha'] <= 0:
                continue
            surf = font.render(j['text'], True, j['color'])
            surf.set_alpha(j['alpha'])
            self.screen.blit(surf, (j['x'] - surf.get_width() // 2, j['y']))

    def _draw_hud(self):
        """Affiche le HUD : score et nom de la musique (dans la zone des pistes)."""
        lane_cx = _LANE_LEFT + _LANE_AREA_W // 2

        # --- Score ---
        sc = self._fonts['score'].render(f"{self.score:,}", True, _COL_WHITE)
        self.screen.blit(sc, (_LANE_LEFT, 10))

        # --- Nom de la musique ---
        name = self._fonts['info'].render(self.music_name, True, (120, 120, 120))
        self.screen.blit(name, (lane_cx - name.get_width() // 2, 55))

    def _draw_side_stats(self):
        """Affiche les statistiques sur tout le côté droit de l'écran."""
        panel_x = _LANE_LEFT + _LANE_AREA_W
        panel_w = self.width - panel_x
        pad     = 20
        cx      = panel_x + panel_w // 2

        # Fond et bordure gauche
        pygame.draw.rect(self.screen, (14, 14, 35), (panel_x, 0, panel_w, self.height))
        pygame.draw.line(self.screen, (60, 60, 90), (panel_x, 0), (panel_x, self.height), 2)

        font_title = pygame.font.Font(None, 46)
        font_lbl   = pygame.font.Font(None, 32)
        font_val   = pygame.font.Font(None, 76)
        font_combo = pygame.font.Font(None, 58)

        # ── Titre ──
        y = 16
        t = font_title.render("STATS", True, _COL_WHITE)
        self.screen.blit(t, (cx - t.get_width() // 2, y))
        y += t.get_height() + 10
        pygame.draw.line(self.screen, (60, 60, 90), (panel_x + pad, y), (self.width - pad, y), 1)
        y += 12

        # ── Barre de vie ──
        lbl = font_lbl.render("VIE", True, _COL_GRAY)
        self.screen.blit(lbl, (cx - lbl.get_width() // 2, y))
        y += lbl.get_height() + 4
        bar_w = panel_w - pad * 2
        pygame.draw.rect(self.screen, (40, 40, 40), (panel_x + pad, y, bar_w, 22), border_radius=11)
        fill_w = int(bar_w * self.health / 100)
        if self.health > 50:
            h_col = _COL_HEALTH_HI
        elif self.health > 25:
            h_col = _COL_HEALTH_MID
        else:
            h_col = _COL_HEALTH_LO
        if fill_w > 0:
            pygame.draw.rect(self.screen, h_col, (panel_x + pad, y, fill_w, 22), border_radius=11)
        pygame.draw.rect(self.screen, _COL_GRAY, (panel_x + pad, y, bar_w, 22), 2, border_radius=11)
        y += 22 + 12
        pygame.draw.line(self.screen, (60, 60, 90), (panel_x + pad, y), (self.width - pad, y), 1)
        y += 12

        # ── Combo courant ──
        if self.combo > 1:
            multi  = min(4, 1 + self.combo // 10)
            c_s    = font_combo.render(f"x{self.combo}", True, _COL_PERFECT)
            self.screen.blit(c_s, (cx - c_s.get_width() // 2, y))
            y += c_s.get_height() + 2
            if multi > 1:
                m_s = font_lbl.render(f"×{multi} multiplicateur", True, _COL_PERFECT)
                self.screen.blit(m_s, (cx - m_s.get_width() // 2, y))
                y += m_s.get_height() + 4
        else:
            y += 4
        pygame.draw.line(self.screen, (60, 60, 90), (panel_x + pad, y), (self.width - pad, y), 1)
        y += 12

        # ── Statistiques ──
        total = self.perfect_count + self.good_count + self.miss_count
        acc   = int((self.perfect_count + self.good_count * 0.5) / total * 100) if total > 0 else 0

        rows = [
            ("PERFECT",   str(self.perfect_count), _COL_PERFECT),
            ("GOOD",      str(self.good_count),     _COL_GOOD),
            ("MISS",      str(self.miss_count),      _COL_MISS),
            ("PRÉCISION", f"{acc} %",               _COL_WHITE),
            ("MAX COMBO", f"x{self.max_combo}",     _COL_PERFECT),
        ]

        remaining_h = self.height - y
        row_h       = remaining_h // len(rows)

        for i, (label, value, color) in enumerate(rows):
            cy    = y + i * row_h + row_h // 2
            lbl_s = font_lbl.render(label, True, _COL_GRAY)
            val_s = font_val.render(value, True, color)
            self.screen.blit(lbl_s, (cx - lbl_s.get_width() // 2, cy - lbl_s.get_height() // 2 - 18))
            self.screen.blit(val_s, (cx - val_s.get_width() // 2, cy - val_s.get_height() // 2 + 10))
            if i < len(rows) - 1:
                sep_y = y + (i + 1) * row_h
                pygame.draw.line(self.screen, (35, 35, 60),
                                 (panel_x + pad, sep_y), (self.width - pad, sep_y), 1)

    def _draw_pause_overlay(self):
        """Superpose un écran de pause semi-transparent."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill(_COL_OVERLAY)
        self.screen.blit(overlay, (0, 0))

        font = pygame.font.Font(None, 110)
        txt  = font.render("PAUSE", True, _COL_WHITE)
        self.screen.blit(txt, (self.width // 2 - txt.get_width() // 2, self.height // 2 - 60))

        hint = self._fonts['info'].render(
            "P  Reprendre     ÉCHAP  Menu", True, _COL_GRAY
        )
        self.screen.blit(hint, (self.width // 2 - hint.get_width() // 2, self.height // 2 + 60))

    def _draw_result(self):
        """Affiche l'écran de résultat en surimpression."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill(_COL_OVERLAY)
        self.screen.blit(overlay, (0, 0))

        # Titre
        if self.health > 0:
            title_txt   = "TERMINÉ !"
            title_color = _COL_PERFECT
        else:
            title_txt   = "ÉCHEC..."
            title_color = _COL_MISS

        title = self._fonts['result'].render(title_txt, True, title_color)
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 175))

        # Statistiques
        total = self.perfect_count + self.good_count + self.miss_count
        acc   = (
            int((self.perfect_count + self.good_count * 0.5) / total * 100)
            if total > 0 else 0
        )

        stats = [
            (f"Score",          f"{self.score:,}",        _COL_WHITE),
            (f"Max Combo",      f"x{self.max_combo}",     _COL_WHITE),
            (f"Précision",      f"{acc} %",               _COL_WHITE),
            (f"PERFECT",        str(self.perfect_count),  _COL_PERFECT),
            (f"GOOD",           str(self.good_count),     _COL_GOOD),
            (f"MISS",           str(self.miss_count),     _COL_MISS),
        ]

        font_lbl = self._fonts['combo']
        font_val = self._fonts['score']
        y0       = 310
        row_h    = 68
        col_lbl  = self.width // 2 - 200
        col_val  = self.width // 2 + 80

        for i, (label, value, color) in enumerate(stats):
            lbl_s = font_lbl.render(label, True, _COL_GRAY)
            val_s = font_val.render(value, True, color)
            self.screen.blit(lbl_s, (col_lbl - lbl_s.get_width(), y0 + i * row_h))
            self.screen.blit(val_s, (col_val, y0 + i * row_h))

        hint = self._fonts['info'].render(
            "F  Retour au menu", True, _COL_GRAY
        )
        self.screen.blit(hint, (self.width // 2 - hint.get_width() // 2, self.height - 70))
