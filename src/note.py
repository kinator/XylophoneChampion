"""
Classe Note et constantes de jeu pour Xylophone Champion.

Auteurs: Julien Behani, Enzo Fournier - 2026
"""

# Nombre de pistes
NUM_LANES = 5

# Couleurs des pistes, inspirées d'un xylophone (rouge → bleu)
LANE_COLORS = [
    (230,  60,  60),   # Rouge
    (230, 150,  50),   # Orange
    (220, 220,  50),   # Jaune
    ( 60, 190,  70),   # Vert
    ( 60, 110, 230),   # Bleu
]

# Touches associées à chaque piste — boutons J1 de la borne arcade
# Rangée basse : F G H (pistes 0-1-2) | Rangée haute : R T (pistes 3-4)
LANE_KEYS_DISPLAY = ['F', 'G', 'H', 'R', 'T']

# Fenêtres de jugement en secondes
PERFECT_WINDOW = 0.07   # ±70 ms → PERFECT
GOOD_WINDOW    = 0.15   # ±150 ms → GOOD

# Points de base par jugement (multipliés ensuite par le combo)
JUDGMENT_POINTS = {
    'perfect': 100,
    'good':     50,
    'miss':      0,
}

# Vitesse de chute des notes (pixels par seconde)
FALL_SPEED = 420

# Hauteur de la zone de frappe (pixels depuis le haut de l'écran)
HIT_Y = 870

# Hauteur visuelle d'une note (pixels)
NOTE_HEIGHT = 22


class Note:
    """
    Représente une note tombante dans une piste.

    Attributs:
        lane (int): Indice de la piste (0-4).
        time (float): Instant exact (en secondes) où la note doit être frappée.
        hit (bool): True si la note a été frappée.
        missed (bool): True si la note a été ratée.
        judgment (str | None): Jugement attribué ('perfect', 'good', 'miss').
    """

    def __init__(self, lane: int, time: float):
        self.lane = lane
        self.time = time
        self.hit = False
        self.missed = False
        self.judgment = None

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    def get_y(self, current_time: float) -> int:
        """
        Calcule la position Y de la note en fonction du temps courant.

        Args:
            current_time: Temps actuel en secondes depuis le début de la musique.

        Returns:
            Position Y en pixels (peut être négative ou > hauteur d'écran).
        """
        return int(HIT_Y - (self.time - current_time) * FALL_SPEED)

    # ------------------------------------------------------------------
    # Logique de frappe
    # ------------------------------------------------------------------

    def try_hit(self, current_time: float) -> str | None:
        """
        Tente de frapper la note au temps donné.

        Args:
            current_time: Temps actuel en secondes.

        Returns:
            Le jugement obtenu ('perfect' ou 'good'), ou None si hors fenêtre.
        """
        if self.hit or self.missed:
            return None

        diff = abs(current_time - self.time)

        if diff <= PERFECT_WINDOW:
            self.hit = True
            self.judgment = 'perfect'
            return 'perfect'

        if diff <= GOOD_WINDOW:
            self.hit = True
            self.judgment = 'good'
            return 'good'

        return None

    def check_missed(self, current_time: float) -> bool:
        """
        Vérifie si la note est passée sans être frappée.

        Args:
            current_time: Temps actuel en secondes.

        Returns:
            True si la note vient d'être marquée comme ratée.
        """
        if not self.hit and not self.missed:
            if current_time > self.time + GOOD_WINDOW:
                self.missed = True
                self.judgment = 'miss'
                return True
        return False

    def is_active(self) -> bool:
        """Retourne True si la note n'a pas encore été traitée."""
        return not self.hit and not self.missed
