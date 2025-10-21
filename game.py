# game.py — Goalie clicker final
# Requires: pygame
# Place level_config.json and assets (keepL.png keepR.png optional sounds) in ./assets/

import os, sys, json, math, random, time
import pygame
import webbrowser  # Добавляем для открытия ссылок

# ---------- Config ----------
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
CFG_PATH = os.path.join(ASSETS_DIR, "level_config.json")

FPS = 60
ASPECT_W, ASPECT_H = 16, 9
PUCK_RADIUS = 14
START_LIVES = 3
MAX_SPEED_MULT = 10  # Увеличена максимальная скорость
SPEED_RAMP_TIME = 120.0  # seconds to reach max multiplier

# ---------- Helpers ----------
def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_image(path):
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        return None

def find_asset(name):
    p = os.path.join(ASSETS_DIR, name)
    return p if os.path.exists(p) else None

# ---------- Game classes ----------
class Puck:
    def __init__(self, sx, sy, tx, ty, base_speed):
        self.x = sx; self.y = sy
        self.tx = tx; self.ty = ty
        dx = tx - sx; dy = ty - sy
        d = math.hypot(dx, dy) or 1.0
        self.vx = dx / d * base_speed
        self.vy = dy / d * base_speed
        self.fade = False
        self.opacity = 255
        self.alive = True

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.fade:
            # Вместо плавного исчезания - сразу удаляем
            self.alive = False

    def draw(self, surf, ox, oy):
        # draw as circle with alpha
        s = pygame.Surface((PUCK_RADIUS*2, PUCK_RADIUS*2), pygame.SRCALPHA)
        col = (0, 0, 0, int(max(0, min(255, self.opacity))))
        pygame.draw.circle(s, col, (PUCK_RADIUS, PUCK_RADIUS), PUCK_RADIUS)
        surf.blit(s, (ox + int(self.x) - PUCK_RADIUS, oy + int(self.y) - PUCK_RADIUS))

# ---------- Main game ----------
class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.pre_init(44100, -16, 2, 512)
        
        # Определяем платформу
        self.is_mobile = self.detect_mobile()
        
        # Настройки экрана для разных платформ
        if self.is_mobile:
            # Для мобильных - полноэкранный режим
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.screen_w, self.screen_h = self.screen.get_size()
            # Используем меньший шрифт для мобильных
            self.font = pygame.font.SysFont("Arial", 20)
            self.small = pygame.font.SysFont("Arial", 14)
        else:
            # Для ПК - обычный полноэкранный
            self.info = pygame.display.Info()
            self.screen_w = self.info.current_w
            self.screen_h = self.info.current_h
            self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.FULLSCREEN)
            self.font = pygame.font.SysFont("Arial", 22)
            self.small = pygame.font.SysFont("Arial", 16)
            
        pygame.display.set_caption("Goalie Clicker")
        self.clock = pygame.time.Clock()
        self.big_font = pygame.font.SysFont("Arial", 48, bold=True)  # Для надписи "ГОЛ"

        # Отладочный режим
        self.debug_mode = False
        self.infinite_lives = False

        # compute centered 16:9 rect
        self.compute_game_rect()

        # load config
        self.cfg = load_json(CFG_PATH) or {}
        self.load_scene_from_config()

        # sounds
        self.snd_game = None
        self.snd_save = None
        self.snd_miss = None
        self.load_sounds()

        self.muted = False
        
        # Кнопки - разные размеры для мобильных и ПК
        if self.is_mobile:
            self.mute_button_rect = pygame.Rect(0, 0, 140, 40)
            self.subscribe_button_rect = pygame.Rect(0, 0, 200, 45)
        else:
            self.mute_button_rect = pygame.Rect(0, 0, 120, 30)
            self.subscribe_button_rect = pygame.Rect(0, 0, 180, 35)
            
        self.vk_url = "https://vk.com/club233320861"

        # gameplay
        self.reset_game_state()

        # UI
        self.show_start_screen = True
        self.show_game_over = False

        # Анимация "ГОЛ"
        self.show_goal_text = False
        self.goal_text_timer = 0.0
        self.goal_text_duration = 2.0

    def detect_mobile(self):
        """Определяем мобильное устройство"""
        try:
            # Проверяем наличие сенсорного ввода
            if pygame.display.get_driver() in ['android', 'iOS']:
                return True
            # Для веб-версии проверяем размер экрана
            info = pygame.display.Info()
            return info.current_h > info.current_w  # Портретный режим
        except:
            return False

    def compute_game_rect(self):
        max_w = int(self.screen_w * 0.95)
        max_h = int(self.screen_h * 0.95)
        target_w = max_w
        target_h = int(target_w * ASPECT_H / ASPECT_W)
        if target_h > max_h:
            target_h = max_h
            target_w = int(target_h * ASPECT_W / ASPECT_H)
        gx = (self.screen_w - target_w) // 2
        gy = (self.screen_h - target_h) // 2
        self.game_rect = pygame.Rect(gx, gy, target_w, target_h)

    def load_scene_from_config(self):
        # background
        self.bg_surf = None
        self.bg_x = 0; self.bg_y = 0; self.bg_scale = 1.0
        bg = self.cfg.get("bg")
        if bg:
            p = bg.get("path")
            if p:
                candidate = os.path.join(ASSETS_DIR, os.path.basename(p))
                if os.path.exists(candidate):
                    self.bg_surf = load_image(candidate)
                    self.bg_scale = bg.get("scale", 1.0)
                    self.bg_x = int(bg.get("x_rel", 0.0) * self.game_rect.w)
                    self.bg_y = int(bg.get("y_rel", 0.0) * self.game_rect.h)

        # goalies
        self.goalieL_surf = None
        self.goalieR_surf = None
        self.goalieL_x = int(self.game_rect.w * 0.22)
        self.goalieL_y = int(self.game_rect.h * 0.55)
        self.goalieR_x = int(self.game_rect.w * 0.62)
        self.goalieR_y = int(self.game_rect.h * 0.55)
        self.goalieL_scale = 1.0
        self.goalieR_scale = 1.0

        gL = self.cfg.get("goalieL")
        if gL:
            p = gL.get("img")
            if p:
                path = os.path.join(ASSETS_DIR, os.path.basename(p))
                if os.path.exists(path):
                    self.goalieL_surf = load_image(path)
            self.goalieL_x = int(gL.get("x_rel", 0.22) * self.game_rect.w)
            self.goalieL_y = int(gL.get("y_rel", 0.55) * self.game_rect.h)
            self.goalieL_scale = gL.get("scale", 1.0)

        gR = self.cfg.get("goalieR")
        if gR:
            p = gR.get("img")
            if p:
                path = os.path.join(ASSETS_DIR, os.path.basename(p))
                if os.path.exists(path):
                    self.goalieR_surf = load_image(path)
            self.goalieR_x = int(gR.get("x_rel", 0.62) * self.game_rect.w)
            self.goalieR_y = int(gR.get("y_rel", 0.55) * self.game_rect.h)
            self.goalieR_scale = gR.get("scale", 1.0)

        # markers (spawns and targets)
        self.spawns = []
        self.targets = []
        for s in self.cfg.get("spawns", []):
            self.spawns.append((s["x_rel"] * self.game_rect.w, s["y_rel"] * self.game_rect.h))
        for t in self.cfg.get("targets", []):
            self.targets.append((t["x_rel"] * self.game_rect.w, t["y_rel"] * self.game_rect.h))

        # line
        if self.cfg.get("line"):
            self.line_y = int(self.cfg["line"].get("y_rel", 0.78) * self.game_rect.h)
        else:
            self.line_y = int(self.game_rect.h * 0.78)

    def load_sounds(self):
        try:
            p = find_asset("game.mp3")
            if p: 
                self.snd_game = pygame.mixer.Sound(p)
                self.snd_game.set_volume(0.7)
            
            p = find_asset("save.mp3") or find_asset("Звук пойманной шайбы.mp3") or find_asset("save.MP3")
            if p: 
                self.snd_save = pygame.mixer.Sound(p)
                self.snd_save.set_volume(1.0)
            
            p = find_asset("propusk.mp3") or find_asset("prpusk.MP3")
            if p: 
                self.snd_miss = pygame.mixer.Sound(p)
                self.snd_miss.set_volume(1.0)
        except Exception as e:
            print(f"Ошибка загрузки звуков: {e}")
            self.snd_game = self.snd_save = self.snd_miss = None

    def reset_game_state(self):
        self.pucks = []
        self.spawn_timer = 0.0
        self.base_spawn_interval = 0.9
        self.score = 0
        self.lives = START_LIVES
        self.elapsed = 0.0
        self.speed_mult = 1.0
        # current goalie side L or R
        self.goalie_side = "L"
        # ensure there are at least two spawn/targets
        if not self.spawns:
            w,h = self.game_rect.w, self.game_rect.h
            self.spawns = [(int(w*0.08), int(h*0.25)), (int(w*0.92), int(h*0.25))]
        if not self.targets:
            w,h = self.game_rect.w, self.game_rect.h
            self.targets = [(int(w*0.35), int(h*0.45)), (int(w*0.65), int(h*0.45))]
        
        # Сбрасываем анимацию гола
        self.show_goal_text = False
        self.goal_text_timer = 0.0

    def play_bg_music(self):
        if self.snd_game and not self.muted:
            try:
                pygame.mixer.stop()
                self.snd_game.play(loops=-1, fade_ms=1000)
            except Exception as e:
                print(f"Ошибка воспроизведения музыки: {e}")

    def stop_bg_music(self):
        if self.snd_game:
            try:
                self.snd_game.stop()
            except Exception:
                pass

    def play_save_sound(self):
        """Воспроизведение звука сейва - не прерывает предыдущий"""
        if self.snd_save and not self.muted:
            try:
                # Воспроизводим без остановки предыдущего - звуки могут накладываться
                self.snd_save.play()
            except Exception as e:
                print(f"Ошибка воспроизведения звука сейва: {e}")

    def play_miss_sound(self):
        """Воспроизведение звука пропуска гола"""
        if self.snd_miss and not self.muted:
            try:
                # Останавливаем все звуки сейва перед воспроизведением пропуска
                if self.snd_save:
                    self.snd_save.stop()
                self.snd_miss.play()
            except Exception as e:
                print(f"Ошибка воспроизведения звука пропуска: {e}")

    def spawn_puck(self):
        si = random.randrange(len(self.spawns))
        ti = random.randrange(len(self.targets))
        sx, sy = self.spawns[si]
        tx, ty = self.targets[ti]
        base_speed = random.uniform(260, 360) * self.speed_mult
        p = Puck(sx, sy, tx, ty, base_speed)
        self.pucks.append(p)

    def handle_click_toggle_goalie(self):
        # toggle side
        self.goalie_side = "R" if self.goalie_side == "L" else "L"

    def draw_goalie(self):
        gr = self.game_rect
        if self.goalie_side == "L" and self.goalieL_surf:
            img = pygame.transform.smoothscale(self.goalieL_surf, (int(self.goalieL_surf.get_width()*self.goalieL_scale), int(self.goalieL_surf.get_height()*self.goalieL_scale)))
            self.screen.blit(img, (gr.x + int(self.goalieL_x), gr.y + int(self.goalieL_y)))
        elif self.goalie_side == "R" and self.goalieR_surf:
            img = pygame.transform.smoothscale(self.goalieR_surf, (int(self.goalieR_surf.get_width()*self.goalieR_scale), int(self.goalieR_surf.get_height()*self.goalieR_scale)))
            self.screen.blit(img, (gr.x + int(self.goalieR_x), gr.y + int(self.goalieR_y)))
        else:
            # fallback rectangle marker
            gx = gr.x + (int(gr.w*0.28) if self.goalie_side == "L" else int(gr.w*0.62))
            gy = gr.y + int(gr.h*0.55)
            pygame.draw.rect(self.screen, (12,60,120), (gx-40, gy-40, 80, 80))

    def render_hud(self):
        # lives as hearts
        lives_text = f"Жизней: ∞" if (self.debug_mode and self.infinite_lives) else f"Жизней: {self.lives}"
        txt_score = self.font.render(f"Счёт: {self.score}", True, (255,255,255))
        txt_lives = self.font.render(lives_text, True, (255,180,180))
        self.screen.blit(txt_score, (18, 12))
        self.screen.blit(txt_lives, (18, 42))
        
        # Текстовая кнопка mute
        button_x = int(self.screen_w * 0.74)
        button_y = int(self.screen_h * 0.05)
        self.mute_button_rect = pygame.Rect(button_x, button_y, self.mute_button_rect.width, self.mute_button_rect.height)
        
        # Рисуем кнопку
        button_color = (80, 80, 100) if not self.muted else (120, 60, 60)
        pygame.draw.rect(self.screen, button_color, self.mute_button_rect, border_radius=6)
        pygame.draw.rect(self.screen, (150, 150, 170), self.mute_button_rect, 2, border_radius=6)
        
        # Текст кнопки
        mute_text = "Выкл звук" if not self.muted else "Вкл звук"
        text_surf = self.small.render(mute_text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.mute_button_rect.center)
        self.screen.blit(text_surf, text_rect)
        
        # Отладочная информация
        if self.debug_mode:
            debug_txt = self.small.render(f"DEBUG: Spawns: {len(self.spawns)}, Targets: {len(self.targets)}, LineY: {self.line_y}", True, (255, 100, 100))
            self.screen.blit(debug_txt, (18, 72))

    def draw_goal_text(self):
        """Отрисовка надписи ГОЛ в координатах (0.469, 0.242)"""
        if self.show_goal_text:
            # Вычисляем абсолютные координаты
            goal_x = int(self.screen_w * 0.469)
            goal_y = int(self.screen_h * 0.242)
            
            # Создаем текст с красным цветом и черной обводкой
            goal_text = self.big_font.render("ГОЛ!", True, (255, 50, 50))
            
            # Рисуем черную обводку
            for dx in [-2, 0, 2]:
                for dy in [-2, 0, 2]:
                    if dx != 0 or dy != 0:
                        outline_text = self.big_font.render("ГОЛ!", True, (0, 0, 0))
                        self.screen.blit(outline_text, (goal_x - outline_text.get_width()//2 + dx, goal_y - outline_text.get_height()//2 + dy))
            
            # Рисуем основной текст
            self.screen.blit(goal_text, (goal_x - goal_text.get_width()//2, goal_y - goal_text.get_height()//2))

    def draw_developer_info(self):
        """Отрисовка информации о разработчике внизу экрана"""
        # Разработчик
        dev_text = self.small.render("Разработчик: Петров Дмитрий", True, (200, 200, 200))
        dev_x = self.screen_w // 2 - dev_text.get_width() // 2
        dev_y = self.screen_h - 120
        self.screen.blit(dev_text, (dev_x, dev_y))
        
        # Кнопка ПОДПИСАТЬСЯ
        subscribe_x = self.screen_w // 2 - self.subscribe_button_rect.width // 2
        subscribe_y = self.screen_h - 85
        self.subscribe_button_rect = pygame.Rect(subscribe_x, subscribe_y, self.subscribe_button_rect.width, self.subscribe_button_rect.height)
        
        # Рисуем кнопку подписки
        subscribe_color = (70, 100, 170)  # Синий цвет ВК
        pygame.draw.rect(self.screen, subscribe_color, self.subscribe_button_rect, border_radius=8)
        pygame.draw.rect(self.screen, (100, 130, 200), self.subscribe_button_rect, 2, border_radius=8)
        
        # Текст кнопки
        subscribe_text = self.small.render("ПОДПИСАТЬСЯ", True, (255, 255, 255))
        subscribe_text_rect = subscribe_text.get_rect(center=self.subscribe_button_rect.center)
        self.screen.blit(subscribe_text, subscribe_text_rect)

    def open_vk_community(self):
        """Открытие сообщества ВК в браузере"""
        try:
            webbrowser.open(self.vk_url)
            print(f"Открываю сообщество: {self.vk_url}")
        except Exception as e:
            print(f"Ошибка при открытии ссылки: {e}")

    def draw_debug_markers(self):
        """Отрисовка отладочных маркеров"""
        gr = self.game_rect
        
        # Отрисовка спавнов (зеленые круги)
        for i, (sx, sy) in enumerate(self.spawns):
            pygame.draw.circle(self.screen, (0, 255, 0), (gr.x + int(sx), gr.y + int(sy)), 8)
            spawn_text = self.small.render(f"S{i}", True, (0, 255, 0))
            self.screen.blit(spawn_text, (gr.x + int(sx) + 10, gr.y + int(sy) - 10))
            
            # Координаты спавнов
            coord_text = self.small.render(f"({sx/gr.w:.3f}, {sy/gr.h:.3f})", True, (200, 255, 200))
            self.screen.blit(coord_text, (gr.x + int(sx) + 10, gr.y + int(sy) + 10))
        
        # Отрисовка целей (красные круги)
        for i, (tx, ty) in enumerate(self.targets):
            pygame.draw.circle(self.screen, (255, 0, 0), (gr.x + int(tx), gr.y + int(ty)), 8)
            target_text = self.small.render(f"T{i}", True, (255, 0, 0))
            self.screen.blit(target_text, (gr.x + int(tx) + 10, gr.y + int(ty) - 10))
            
            # Координаты целей
            coord_text = self.small.render(f"({tx/gr.w:.3f}, {ty/gr.h:.3f})", True, (255, 200, 200))
            self.screen.blit(coord_text, (gr.x + int(tx) + 10, gr.y + int(ty) + 10))
        
        # Отрисовка линии (синяя линия)
        line_y_abs = gr.y + self.line_y
        pygame.draw.line(self.screen, (0, 100, 255), (gr.x, line_y_abs), (gr.x + gr.w, line_y_abs), 3)
        line_text = self.small.render(f"Line: {self.line_y/gr.h:.3f}", True, (0, 100, 255))
        self.screen.blit(line_text, (gr.x + 10, line_y_abs + 5))
        
        # Отрисовка траекторий для всех возможных комбинаций спавн-цель
        for sx, sy in self.spawns:
            for tx, ty in self.targets:
                pygame.draw.line(self.screen, (255, 255, 0, 100), 
                               (gr.x + int(sx), gr.y + int(sy)), 
                               (gr.x + int(tx), gr.y + int(ty)), 1)

    def draw_cursor_coordinates(self):
        """Отрисовка координат под курсором"""
        mx, my = pygame.mouse.get_pos()
        gr = self.game_rect
        
        # Проверяем, находится ли курсор внутри игровой области
        if gr.collidepoint(mx, my):
            # Вычисляем относительные координаты (0.0-1.0)
            rel_x = (mx - gr.x) / gr.w
            rel_y = (my - gr.y) / gr.h
            
            # Отрисовываем координаты рядом с курсором
            coord_text = self.small.render(f"({rel_x:.3f}, {rel_y:.3f})", True, (255, 255, 255))
            text_rect = coord_text.get_rect()
            text_rect.topleft = (mx + 15, my + 15)
            
            # Фон для текста для лучшей читаемости
            pygame.draw.rect(self.screen, (0, 0, 0, 180), 
                           (text_rect.x - 2, text_rect.y - 2, 
                            text_rect.width + 4, text_rect.height + 4))
            self.screen.blit(coord_text, text_rect)

    def run(self):
        running = True
        self.play_bg_music()
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self.elapsed += dt
            
            # Обновляем таймер надписи ГОЛ
            if self.show_goal_text:
                self.goal_text_timer += dt
                if self.goal_text_timer >= self.goal_text_duration:
                    self.show_goal_text = False
                    self.goal_text_timer = 0.0
            
            # gradually ramp speed multiplier from 1.0 to MAX_SPEED_MULT over SPEED_RAMP_TIME seconds
            t = min(self.elapsed, SPEED_RAMP_TIME) / max(1e-6, SPEED_RAMP_TIME)
            self.speed_mult = 1.0 + (MAX_SPEED_MULT - 1.0) * t

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False; break
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False; break
                    elif ev.key in (pygame.K_LEFT, pygame.K_a):
                        self.goalie_side = "L"
                    elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                        self.goalie_side = "R"
                    elif ev.key == pygame.K_m:
                        self.toggle_mute()
                    elif ev.key == pygame.K_F1:  # Переключение отладочного режима
                        self.debug_mode = not self.debug_mode
                    elif ev.key == pygame.K_F2:  # Переключение бесконечных жизней
                        self.infinite_lives = not self.infinite_lives
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouse_click(ev.pos)
                elif ev.type == pygame.FINGERDOWN:
                    # Обработка касаний для мобильных устройств
                    mx = ev.x * self.screen_w
                    my = ev.y * self.screen_h
                    self.handle_mouse_click((mx, my))

            if self.show_start_screen:
                self.draw_start_screen()
                pygame.display.flip()
                continue

            if self.show_game_over:
                self.draw_game_over()
                pygame.display.flip()
                continue

            # spawn logic: interval reduces slightly as speed increases
            interval = max(0.35, self.base_spawn_interval / (0.9 + 0.1 * self.speed_mult))
            self.spawn_timer += dt
            if self.spawn_timer >= interval:
                self.spawn_timer = 0.0
                self.spawn_puck()

            # update pucks
            for p in list(self.pucks):
                prev_y = p.y
                p.update(dt)
                # detect crossing of invisible line (line_y)
                if (prev_y < self.line_y <= p.y) or (prev_y > self.line_y >= p.y):
                    # determine which half the target belongs to
                    mid = self.game_rect.w * 0.5
                    target_side = "L" if p.tx < mid else "R"
                    if self.goalie_side == target_side:
                        # save
                        p.fade = True
                        p.alive = True
                        self.score += 1
                        self.play_save_sound()
                    else:
                        # miss => remove puck and decrement life (если не бесконечные жизни)
                        p.alive = False
                        if not (self.debug_mode and self.infinite_lives):
                            self.lives -= 1
                        self.play_miss_sound()
                        # Показываем надпись ГОЛ
                        self.show_goal_text = True
                        self.goal_text_timer = 0.0
                        
                        if self.lives <= 0 and not (self.debug_mode and self.infinite_lives):
                            # game over
                            self.show_game_over = True
                            self.stop_bg_music()
                            break
                if not p.alive:
                    try: self.pucks.remove(p)
                    except: pass

            # draw frame
            self.screen.fill((10, 18, 30))
            # game area background
            pygame.draw.rect(self.screen, (14,30,55), self.game_rect)
            # draw bg image if available
            if self.bg_surf:
                bw = int(self.bg_surf.get_width() * self.bg_scale)
                bh = int(self.bg_surf.get_height() * self.bg_scale)
                try:
                    bimg = pygame.transform.smoothscale(self.bg_surf, (bw, bh))
                    self.screen.blit(bimg, (self.game_rect.x + int(self.bg_x), self.game_rect.y + int(self.bg_y)))
                except Exception:
                    pass
            
            # Отрисовка отладочных маркеров если включен режим отладки
            if self.debug_mode:
                self.draw_debug_markers()
            
            # draw pucks
            for p in self.pucks:
                p.draw(self.screen, self.game_rect.x, self.game_rect.y)
            # draw goalie sprite
            self.draw_goalie()
            # HUD
            self.render_hud()
            
            # Отрисовка надписи ГОЛ если нужно
            self.draw_goal_text()
            
            # Отрисовка информации о разработчике
            self.draw_developer_info()
            
            # Отрисовка координат курсора в отладочном режиме
            if self.debug_mode:
                self.draw_cursor_coordinates()

            pygame.display.flip()

        pygame.quit()

    def handle_mouse_click(self, pos):
        """Обработка кликов мыши и касаний"""
        mx, my = pos
        
        if self.show_start_screen:
            if self.is_point_in_start_button(mx, my):
                self.start_game()
            elif self.subscribe_button_rect.collidepoint(mx, my):
                self.open_vk_community()
            else:
                # allow click anywhere to also start
                self.start_game()
        elif self.show_game_over:
            if self.is_point_in_restart_button(mx, my):
                self.start_game()
            elif self.subscribe_button_rect.collidepoint(mx, my):
                self.open_vk_community()
        else:
            # Проверяем клик по кнопке mute
            if self.mute_button_rect.collidepoint(mx, my):
                self.toggle_mute()
            elif self.subscribe_button_rect.collidepoint(mx, my):
                self.open_vk_community()
            else:
                # gameplay click toggles goalie side (as requested)
                self.handle_click_toggle_goalie()

    # ---------- UI screens ----------
    def draw_start_screen(self):
        self.screen.fill((10,18,30))
        pygame.draw.rect(self.screen, (14,30,55), self.game_rect)
        if self.bg_surf:
            bw = int(self.bg_surf.get_width() * self.bg_scale)
            bh = int(self.bg_surf.get_height() * self.bg_scale)
            try:
                bimg = pygame.transform.smoothscale(self.bg_surf, (bw, bh))
                self.screen.blit(bimg, (self.game_rect.x + int(self.bg_x), self.game_rect.y + int(self.bg_y)))
            except: pass
            
        # Отрисовка отладочных маркеров на стартовом экране
        if self.debug_mode:
            self.draw_debug_markers()
            
        # Отрисовка координат курсора на стартовом экране
        if self.debug_mode:
            self.draw_cursor_coordinates()
            
        # big Start button centered inside game_rect (поднята выше)
        btn_w = int(self.game_rect.w * 0.28)
        btn_h = 64
        bx = self.game_rect.x + (self.game_rect.w - btn_w)//2.12
        by = self.game_rect.y + (self.game_rect.h - btn_h)//3
        pygame.draw.rect(self.screen, (255,200,50), (bx, by, btn_w, btn_h), border_radius=10)
        txt = self.font.render("Начать", True, (10,10,10))
        self.screen.blit(txt, (bx + (btn_w - txt.get_width())//2, by + (btn_h - txt.get_height())//2))
        
        # hint
        hint_text = "Клик/тап по экрану — переключить вратаря" if self.is_mobile else "Клик/тап по экрану — переключить вратаря во время игры"
        hint = self.small.render(hint_text, True, (200,200,200))
        self.screen.blit(hint, (self.game_rect.x + 18, self.game_rect.y + self.game_rect.h - 28))
        
        # Отладочная подсказка
        if self.debug_mode:
            debug_hint = self.small.render("DEBUG: F1 - отладка, F2 - беск. жизни, Координаты под курсором", True, (255, 100, 100))
            self.screen.blit(debug_hint, (self.game_rect.x + 18, self.game_rect.y + self.game_rect.h - 50))
        
        # Информация о разработчике на стартовом экране
        self.draw_developer_info()

    def is_point_in_start_button(self, mx, my):
        btn_w = int(self.game_rect.w * 0.28)
        btn_h = 64
        bx = self.game_rect.x + (self.game_rect.w - btn_w)//2.12
        by = self.game_rect.y + (self.game_rect.h - btn_h)//3
        return bx <= mx <= bx+btn_w and by <= my <= by+btn_h

    def start_game(self):
        self.reset_game_state()
        self.show_start_screen = False
        self.show_game_over = False
        self.play_bg_music()

    def draw_game_over(self):
        # overlay game over
        self.screen.fill((0,0,0))
        txt = self.font.render("Игра окончена", True, (255,255,255))
        sc = self.font.render(f"Ваш рекорд: {self.score}", True, (255,255,255))
        self.screen.blit(txt, (self.screen_w//2 - txt.get_width()//2, self.screen_h//2 - 60))
        self.screen.blit(sc, (self.screen_w//2 - sc.get_width()//2, self.screen_h//2 - 20))
        # restart button
        btn_w = 240; btn_h = 56
        bx = self.screen_w//2 - btn_w//2; by = self.screen_h//2 + 36
        pygame.draw.rect(self.screen, (255,200,50), (bx, by, btn_w, btn_h), border_radius=10)
        txt2 = self.font.render("Играть снова", True, (0,0,0))
        self.screen.blit(txt2, (bx + (btn_w - txt2.get_width())//2, by + (btn_h - txt2.get_height())//2))
        
        # Информация о разработчике на экране окончания игры
        self.draw_developer_info()

    def is_point_in_restart_button(self, mx, my):
        btn_w = 240; btn_h = 56
        bx = self.screen_w//2 - btn_w//2; by = self.screen_h//2 + 36
        return bx <= mx <= bx+btn_w and by <= my <= by+btn_h

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            pygame.mixer.pause()
        else:
            pygame.mixer.unpause()
            if self.snd_game and not self.show_start_screen and not self.show_game_over:
                self.snd_game.play(loops=-1, fade_ms=1000)

# ---------- Run ----------
if __name__ == "__main__":
    # ensure assets folder exists
    if not os.path.isdir(ASSETS_DIR):
        print("Создайте папку 'assets' и положите туда level_config.json и спрайты keepL.png/keepR.png")
        sys.exit(1)
    game = Game()
    game.run()