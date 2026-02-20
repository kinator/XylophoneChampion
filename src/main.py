"""
Xylophone Champion - Jeu de rythme style Guitar Hero
Par Julien Behani et Enzo Fournier - 2026

Point d'entrée principal : initialise pygame et gère les transitions
entre le menu de sélection et la scène de jeu.
"""

import os
import sys
import pygame

# S'assurer que le répertoire de travail est bien XylophoneChampion/
# (nécessaire pour retrouver les dossiers music/ et cache/)
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from menu import MenuScene   # noqa: E402  (import après chdir)
from game import GameScene   # noqa: E402

_SCREEN_W = 1280
_SCREEN_H = 1024
_FPS      = 60


def main():
    """
    Boucle principale du jeu.

    Lance le menu de sélection de musique, puis la scène de jeu lorsque
    le joueur choisit une musique. Gère le retour au menu après une partie.
    """
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

    screen = pygame.display.set_mode((_SCREEN_W, _SCREEN_H))
    pygame.display.set_caption("Xylophone Champion")
    clock = pygame.time.Clock()

    scene = MenuScene(screen)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            result = scene.handle_event(event)
            if result:
                if result['action'] == 'play':
                    scene = GameScene(screen, result['music_path'])
                elif result['action'] == 'menu':
                    scene = MenuScene(screen)

        scene.update()
        scene.draw()
        pygame.display.flip()
        clock.tick(_FPS)

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()
