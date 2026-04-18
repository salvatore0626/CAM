import math
import os
import sys
import time
from typing import Optional
from collections import deque

import pygame
import requests

# -----------------------------
# Minimal helicopter map tracker
# -----------------------------
# Requirements:
#   pip install pygame requests
#
# Put your map image next to this script and name it tour_map.png
# Then set the map bounds and tail number below.
# -----------------------------


# App / Display
MAP_IMAGE = "map.png"
WINDOW_SIZE = (1280, 720)
FULLSCREEN = False
FPS = 20

# API / Tracking
TAIL_NUMBER = "N841AK"
POLL_SECONDS = 10
AIRPLANES_LIVE_URL = "https://api.airplanes.live/v2/reg/{tail}"
REQUEST_TIMEOUT_SECONDS = 2.0

# Trail
TRAIL_MINUTES = 7
TRAIL_LINE_WIDTH = 3
TRAIL_COLOR = (65, 65, 65, 110)
TRAIL_MIN_PIXEL_STEP = 2

# Map Bounds
MAP_MAX_LAT = 29.92060
MAP_MIN_LAT = 29.68267
MAP_MIN_LON = -98.34542
MAP_MAX_LON = -97.86065

# Aircraft Marker
HELICOPTER_RADIUS = 8
AIRCRAFT_LABEL_OFFSET_X = 12
AIRCRAFT_LABEL_OFFSET_Y = 12
AIRCRAFT_LABEL_COLOR = (255, 255, 255)

# Helipad
HELIPAD_LAT = 29.80250
HELIPAD_LON = -98.01392

# UI
DEBUG_FONT_SIZE = 16 

# POI
POI_RADIUS = 10
POIS = [
    {
        "name": "Leading Edge",
        "color": (255, 145, 0),
        "lat": 29.80250,
        "lon": -98.01392,
    },
    {
        "name": "Outlets",
        "color": (236,16,16),
        "lat": 29.82487,
        "lon": -97.98880,
    },
    {
        "name": "Ski Ranch",
        "color": (73,49,232),
        "lat": 29.77268,
        "lon": -98.03860,
    },
    {
        "name": "Texas State",
        "color": (5,192,36),
        "lat": 29.88595,
        "lon": -97.94699,
    },
    {
        "name": "Water Park",
        "color": (255,162,21),
        "lat": 29.71336,
        "lon": -98.12574,
    },
    {
        "name": "Canyon Lake",
        "color": (246,198,4),
        "lat": 29.86199,
        "lon": -98.20065,
    },
    {
        "name": "Guadalupe River",
        "color": (173,4,246),
        "lat": 29.79023,
        "lon": -98.15426,
    },
    {
        "name": "Test",
        "color": (50,58,58),
        "lat": 29.74102,
        "lon": -98.09320,
    },
]

class Position:
    def __init__(self, lat: float, lon: float, speed_mph: Optional[float] = None):
        self.lat = lat
        self.lon = lon
        self.speed_mph = speed_mph

class AirplanesLiveSource:
    def __init__(self, tail_number: str, timeout: float = REQUEST_TIMEOUT_SECONDS):
        self.tail_number = tail_number.strip().upper()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "helicopter-tour-prototype/0.1"})

    def get(self) -> Optional[Position]:
        url = AIRPLANES_LIVE_URL.format(tail=self.tail_number)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        aircraft = self._extract_first_aircraft(payload)
        if not aircraft:
            return None

        lat = aircraft.get("lat")
        lon = aircraft.get("lon")
        if lat is None or lon is None:
            return None

        # Airplanes.live "gs" is ground speed in knots
        gs_knots = aircraft.get("gs")
        speed_mph = None
        if gs_knots is not None:
            try:
                speed_mph = float(gs_knots) * 1.15078
            except (TypeError, ValueError):
                speed_mph = None

        return Position(float(lat), float(lon), speed_mph)

    @staticmethod
    def _extract_first_aircraft(payload: dict) -> Optional[dict]:
        if isinstance(payload, dict):
            if isinstance(payload.get("ac"), list) and payload["ac"]:
                return payload["ac"][0]
            if isinstance(payload.get("aircraft"), list) and payload["aircraft"]:
                return payload["aircraft"][0]
            if isinstance(payload.get("response"), list) and payload["response"]:
                return payload["response"][0]
        return None

def latlon_to_xy(lat: float, lon: float, width: int, height: int) -> tuple[int, int]:
    lon_span = MAP_MAX_LON - MAP_MIN_LON
    lat_span = MAP_MAX_LAT - MAP_MIN_LAT
    if lon_span <= 0 or lat_span <= 0:
        raise ValueError("Invalid map bounds.")

    x_ratio = (lon - MAP_MIN_LON) / lon_span
    y_ratio = (MAP_MAX_LAT - lat) / lat_span

    x = round(x_ratio * width)
    y = round(y_ratio * height)
    return x, y

def point_in_bounds(lat: float, lon: float) -> bool:
    return MAP_MIN_LAT <= lat <= MAP_MAX_LAT and MAP_MIN_LON <= lon <= MAP_MAX_LON

def load_map_surface(size: tuple[int, int]) -> pygame.Surface:
    if not os.path.exists(MAP_IMAGE):
        raise FileNotFoundError(f"Map image '{MAP_IMAGE}' not found.")
    image = pygame.image.load(MAP_IMAGE)
    return pygame.transform.smoothscale(image, size)

def miles_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_miles = 3958.8

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_miles * c

def draw_pois(screen: pygame.Surface, font: pygame.font.Font) -> None:
    for poi in POIS:
        lat = poi["lat"]
        lon = poi["lon"]

        if not point_in_bounds(lat, lon):
            continue

        x, y = latlon_to_xy(lat, lon, *WINDOW_SIZE)
        color = poi["color"]
        name = poi["name"]

        pygame.draw.circle(screen, color, (x, y), POI_RADIUS)
        pygame.draw.circle(screen, (255, 255, 255), (x, y), POI_RADIUS + 2, 2)

        label_surface = font.render(name, True, (255, 255, 255))
        label_rect = label_surface.get_rect(
            midbottom=(x, y - POI_RADIUS - 8)
        )

        label_bg_rect = label_rect.inflate(8, 4)
        label_bg = pygame.Surface((label_bg_rect.width, label_bg_rect.height), pygame.SRCALPHA)
        label_bg.fill((0, 0, 0, 140))

        screen.blit(label_bg, label_bg_rect.topleft)
        screen.blit(label_surface, label_rect.topleft)

def prune_trail(trail_points: deque, now: float) -> None:
    cutoff = now - (TRAIL_MINUTES * 60)
    while trail_points and trail_points[0][0] < cutoff:
        trail_points.popleft()


def add_trail_point(trail_points: deque, now: float, lat: float, lon: float) -> None:
    if not point_in_bounds(lat, lon):
        return

    x, y = latlon_to_xy(lat, lon, *WINDOW_SIZE)

    # Skip points that would land almost on top of the last one
    if trail_points:
        _, last_x, last_y = trail_points[-1]
        if abs(x - last_x) < TRAIL_MIN_PIXEL_STEP and abs(y - last_y) < TRAIL_MIN_PIXEL_STEP:
            return

    trail_points.append((now, x, y))


def draw_trail(trail_surface: pygame.Surface, trail_points: deque) -> None:
    trail_surface.fill((0, 0, 0, 0))

    if len(trail_points) < 2:
        return

    points = [(x, y) for _, x, y in trail_points]
    pygame.draw.lines(trail_surface, TRAIL_COLOR, False, points, TRAIL_LINE_WIDTH)

def main() -> None:
    pygame.init()
    pygame.font.init()
    flags = pygame.FULLSCREEN if FULLSCREEN else 0
    screen = pygame.display.set_mode(WINDOW_SIZE, flags)
    pygame.display.set_caption("Helicopter Tour Tracker")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, DEBUG_FONT_SIZE)
    aircraft_label_font = pygame.font.Font(None, 14)

    map_surface = load_map_surface(WINDOW_SIZE)
    trail_surface = pygame.Surface(WINDOW_SIZE, pygame.SRCALPHA)
    source = AirplanesLiveSource(TAIL_NUMBER)

    latest_position: Optional[Position] = None
    last_poll_time = 0.0

    trail_points = deque()

    running = True
    while running:
        now = time.time()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

        if now - last_poll_time >= POLL_SECONDS:
            last_poll_time = now
            try:
                latest_position = source.get()
                if latest_position:
                    add_trail_point(trail_points, now, latest_position.lat, latest_position.lon)
            except Exception:
                pass

        prune_trail(trail_points, now)

        screen.blit(map_surface, (0, 0))
        draw_trail(trail_surface, trail_points)
        screen.blit(trail_surface, (0, 0))
        draw_pois(screen, font)

        # Draw tracked aircraft
        if latest_position and point_in_bounds(latest_position.lat, latest_position.lon):
            x, y = latlon_to_xy(latest_position.lat, latest_position.lon, *WINDOW_SIZE)
            pygame.draw.circle(screen, (255, 239, 0), (x, y), HELICOPTER_RADIUS)
            pygame.draw.circle(screen, (255, 255, 255), (x, y), HELICOPTER_RADIUS + 3, 2)

            tail_surface = aircraft_label_font.render(TAIL_NUMBER, True, AIRCRAFT_LABEL_COLOR)
            tail_rect = tail_surface.get_rect(
                topleft=(x + AIRCRAFT_LABEL_OFFSET_X, y + AIRCRAFT_LABEL_OFFSET_Y)
            )

            tail_bg_rect = tail_rect.inflate(8, 4)
            tail_bg = pygame.Surface((tail_bg_rect.width, tail_bg_rect.height), pygame.SRCALPHA)
            tail_bg.fill((0, 0, 0, 140))

            screen.blit(tail_bg, tail_bg_rect.topleft)
            screen.blit(tail_surface, tail_rect.topleft)

        if latest_position:
            distance_miles = miles_between(
                HELIPAD_LAT,
                HELIPAD_LON,
                latest_position.lat,
                latest_position.lon,
            )

            speed_text = (
                f"{latest_position.speed_mph:.0f} mph"
                if latest_position.speed_mph is not None
                else "waiting"
            )

            debug_text = (
                f"Lat: {latest_position.lat:.6f}   "
                f"Lon: {latest_position.lon:.6f}   "
                f"Dist: {distance_miles:.1f} mi   "
                f"Speed: {speed_text}"
            )
        else:
            debug_text = "Lat: waiting   Lon: waiting   Dist: waiting   Speed: waiting"

        debug_surface = font.render(debug_text, True, (255, 255, 255))
        debug_bg = pygame.Surface((debug_surface.get_width() + 20, debug_surface.get_height() + 12))
        debug_bg.set_alpha(170)
        debug_bg.fill((0, 0, 0))
        screen.blit(debug_bg, (12, 12))
        screen.blit(debug_surface, (22, 18))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()