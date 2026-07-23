"""
SpinGrid Quest
==============
Game kasual orisinal bergaya Slingo (slot + bingo) yang dibangun sepenuhnya
dengan Python & Streamlit. Semua aset visual, nama, dan identitas game
adalah orisinal — tidak ada elemen berhak cipta pihak ketiga yang disalin.

Jalankan secara lokal:
    streamlit run main.py
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import streamlit as st

# =============================================================================
# KONSTANTA & KONFIGURASI GAME
# =============================================================================

BOARD_SIZE = 5
COLUMN_LABELS: List[str] = ["S", "P", "I", "N", "G"]
COLUMN_RANGES: List[Tuple[int, int]] = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]
FREE_CELL = (2, 2)  # (row, col) — sel tengah papan, otomatis ditandai sebagai Wild Star

LINE_SCORE = 100
DIAGONAL_SCORE = 150
FULL_HOUSE_BONUS = 1000
COIN_BONUS_BASE = 50
MULTIPLIER_STEP = 0.5
MULTIPLIER_CAP = 5.0

BONUS_SYMBOLS = ("wild", "extra", "mult", "coin", "blocker")

BONUS_ICON = {
    "wild": "⭐",
    "extra": "🔄",
    "mult": "✨",
    "coin": "🪙",
    "blocker": "🚫",
}
BONUS_NAME = {
    "wild": "Wild",
    "extra": "Extra Spin",
    "mult": "Multiplier",
    "coin": "Coin Bonus",
    "blocker": "Blocker",
}

DIFFICULTY_SETTINGS: Dict[str, Dict] = {
    "Easy": {
        "spins": 22,
        "bonus_prob": 0.30,
        "weights": {"wild": 0.24, "extra": 0.20, "mult": 0.18, "coin": 0.18, "blocker": 0.20},
    },
    "Normal": {
        "spins": 19,
        "bonus_prob": 0.24,
        "weights": {"wild": 0.20, "extra": 0.14, "mult": 0.14, "coin": 0.18, "blocker": 0.34},
    },
    "Hard": {
        "spins": 16,
        "bonus_prob": 0.18,
        "weights": {"wild": 0.16, "extra": 0.08, "mult": 0.11, "coin": 0.15, "blocker": 0.50},
    },
}

# 12 garis: 5 baris, 5 kolom, 2 diagonal
def _build_lines() -> List[Dict]:
    lines = []
    for r in range(BOARD_SIZE):
        lines.append({"id": f"row-{r}", "kind": "row", "cells": [(r, c) for c in range(BOARD_SIZE)]})
    for c in range(BOARD_SIZE):
        lines.append({"id": f"col-{c}", "kind": "col", "cells": [(r, c) for r in range(BOARD_SIZE)]})
    lines.append({"id": "diag-main", "kind": "diag", "cells": [(i, i) for i in range(BOARD_SIZE)]})
    lines.append({"id": "diag-anti", "kind": "diag", "cells": [(i, BOARD_SIZE - 1 - i) for i in range(BOARD_SIZE)]})
    return lines


ALL_LINES = _build_lines()


# =============================================================================
# LOGIKA PERMAINAN (murni, mudah diuji secara terpisah dari UI)
# =============================================================================

def create_board() -> List[List[Optional[int]]]:
    """Buat papan 5x5. Setiap kolom berisi 5 angka unik dari rentangnya sendiri.
    Sel tengah (FREE_CELL) diisi None untuk menandai slot bebas (Wild Star)."""
    board: List[List[Optional[int]]] = [[None] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    for col, (lo, hi) in enumerate(COLUMN_RANGES):
        numbers = random.sample(range(lo, hi + 1), BOARD_SIZE)
        for row in range(BOARD_SIZE):
            board[row][col] = numbers[row]
    board[FREE_CELL[0]][FREE_CELL[1]] = None
    return board


def create_marked_grid() -> List[List[bool]]:
    """Buat grid status tanda, dengan sel tengah otomatis ditandai."""
    marked = [[False] * BOARD_SIZE for _ in range(BOARD_SIZE)]
    marked[FREE_CELL[0]][FREE_CELL[1]] = True
    return marked


def draw_column_symbol(col: int, settings: Dict) -> Dict:
    """Hasilkan satu simbol/angka untuk sebuah kolom pada satu spin."""
    if random.random() < settings["bonus_prob"]:
        symbol_type = random.choices(BONUS_SYMBOLS, weights=[settings["weights"][b] for b in BONUS_SYMBOLS], k=1)[0]
        return {"type": symbol_type, "value": None, "col": col}
    lo, hi = COLUMN_RANGES[col]
    return {"type": "number", "value": random.randint(lo, hi), "col": col}


def find_completed_lines(marked: List[List[bool]], already_completed: set) -> List[Dict]:
    """Cari garis yang baru saja lengkap (belum pernah dihitung sebelumnya)."""
    newly_completed = []
    for line in ALL_LINES:
        if line["id"] in already_completed:
            continue
        if all(marked[r][c] for r, c in line["cells"]):
            newly_completed.append(line)
    return newly_completed


def is_full_house(marked: List[List[bool]]) -> bool:
    return all(marked[r][c] for r in range(BOARD_SIZE) for c in range(BOARD_SIZE))


# =============================================================================
# STATE MANAGEMENT (st.session_state)
# =============================================================================

def init_app_state() -> None:
    """Inisialisasi state aplikasi. Menggunakan pengecekan per-key (bukan satu
    flag tunggal) agar tetap tangguh terhadap sesi browser lama yang masih
    terhubung saat kode di-redeploy (mis. di Streamlit Community Cloud)."""
    st.session_state.setdefault("game_status", "setup")  # setup -> playing -> over / won
    st.session_state.setdefault("difficulty", "Normal")
    st.session_state.setdefault("high_score", 0)
    st.session_state.setdefault("animations_on", True)
    st.session_state.setdefault("sound_on", False)
    if "board" not in st.session_state:
        _reset_round_state()


def _reset_round_state() -> None:
    st.session_state.board = create_board()
    st.session_state.marked = create_marked_grid()
    settings = DIFFICULTY_SETTINGS[st.session_state.difficulty]
    st.session_state.spins_total = settings["spins"]
    st.session_state.spins_remaining = settings["spins"]
    st.session_state.score = 0
    st.session_state.multiplier = 1.0
    st.session_state.completed_lines = set()
    st.session_state.spin_history = []
    st.session_state.last_highlight = []
    st.session_state.spin_count = 0
    st.session_state.win_full_house = False


def start_new_round(difficulty: str) -> None:
    st.session_state.difficulty = difficulty
    _reset_round_state()
    st.session_state.game_status = "playing"


def go_to_setup() -> None:
    st.session_state.game_status = "setup"


def reset_entire_game() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_app_state()


def perform_spin() -> None:
    """Jalankan satu putaran penuh: tarik simbol tiap kolom, terapkan efek,
    tandai papan, hitung skor garis baru, dan perbarui status permainan."""
    if st.session_state.game_status != "playing" or st.session_state.spins_remaining <= 0:
        return

    settings = DIFFICULTY_SETTINGS[st.session_state.difficulty]
    board = st.session_state.board
    marked = st.session_state.marked

    column_results = []
    newly_marked_cells: List[Tuple[int, int]] = []

    st.session_state.spins_remaining -= 1
    st.session_state.spin_count += 1

    for col in range(BOARD_SIZE):
        result = draw_column_symbol(col, settings)
        column_results.append(result)

        if result["type"] == "number":
            value = result["value"]
            for row in range(BOARD_SIZE):
                if board[row][col] == value and not marked[row][col]:
                    marked[row][col] = True
                    newly_marked_cells.append((row, col))
                    break
        elif result["type"] == "wild":
            unmarked_rows = [r for r in range(BOARD_SIZE) if not marked[r][col]]
            if unmarked_rows:
                r = random.choice(unmarked_rows)
                marked[r][col] = True
                newly_marked_cells.append((r, col))
        elif result["type"] == "extra":
            st.session_state.spins_remaining += 1
        elif result["type"] == "mult":
            st.session_state.multiplier = min(MULTIPLIER_CAP, st.session_state.multiplier + MULTIPLIER_STEP)
        elif result["type"] == "coin":
            gain = int(COIN_BONUS_BASE * st.session_state.multiplier)
            st.session_state.score += gain
        # blocker: tidak ada efek

    # Hitung garis baru yang lengkap
    new_lines = find_completed_lines(marked, st.session_state.completed_lines)
    line_score_gained = 0
    for line in new_lines:
        base = DIAGONAL_SCORE if line["kind"] == "diag" else LINE_SCORE
        gained = int(base * st.session_state.multiplier)
        line_score_gained += gained
        st.session_state.completed_lines.add(line["id"])
    st.session_state.score += line_score_gained

    full_house_now = is_full_house(marked)
    if full_house_now and not st.session_state.win_full_house:
        bonus = int(FULL_HOUSE_BONUS * st.session_state.multiplier)
        st.session_state.score += bonus
        st.session_state.win_full_house = True

    # Simpan riwayat
    st.session_state.spin_history.insert(0, {
        "spin_no": st.session_state.spin_count,
        "results": column_results,
        "lines_gained": len(new_lines),
        "score_after": st.session_state.score,
    })
    st.session_state.spin_history = st.session_state.spin_history[:12]
    st.session_state.last_highlight = newly_marked_cells

    # Tentukan status akhir
    if full_house_now:
        st.session_state.game_status = "won"
    elif st.session_state.spins_remaining <= 0:
        st.session_state.game_status = "over"

    st.session_state.high_score = max(st.session_state.high_score, st.session_state.score)


# =============================================================================
# KOMPONEN UI
# =============================================================================

def inject_css() -> None:
    st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .stApp {
        background: radial-gradient(circle at top, #1b1035 0%, #0b0620 55%, #060412 100%);
        color: #f1e9ff;
    }
    h1, h2, h3 { font-family: 'Trebuchet MS', sans-serif; }

    .sg-title {
        text-align: center;
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(90deg, #ffd166, #ef476f, #06d6a0, #118ab2);
        background-size: 300% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: sg-shine 6s linear infinite;
        margin-bottom: 0;
    }
    .sg-subtitle {
        text-align: center;
        color: #b7a9e0;
        margin-top: -8px;
        margin-bottom: 18px;
        font-size: 0.95rem;
        letter-spacing: 1px;
    }
    @keyframes sg-shine {
        to { background-position: 300% center; }
    }

    .sg-board-wrap {
        background: linear-gradient(160deg, #241548, #150c2e);
        border: 2px solid #4b2f8f;
        border-radius: 18px;
        padding: 16px;
        box-shadow: 0 0 30px rgba(120, 80, 255, 0.25);
    }
    .sg-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 8px;
    }
    .sg-header-cell {
        text-align: center;
        font-weight: 800;
        font-size: 1.1rem;
        color: #ffd166;
        padding: 6px 0;
        letter-spacing: 2px;
    }
    .sg-cell {
        aspect-ratio: 1 / 1;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        font-weight: 700;
        font-size: clamp(0.85rem, 2.4vw, 1.25rem);
        background: #1c1240;
        border: 2px solid #3a2870;
        color: #d8cdfa;
        transition: transform 0.15s ease;
    }
    .sg-cell.marked {
        background: linear-gradient(145deg, #06d6a0, #118ab2);
        color: #062b22;
        border-color: #06d6a0;
    }
    .sg-cell.free {
        background: linear-gradient(145deg, #ffd166, #ef476f);
        color: #3a0d1e;
        border-color: #ffd166;
    }
    .sg-cell.highlight {
        animation: sg-pop 0.6s ease;
        box-shadow: 0 0 0 3px #fff, 0 0 18px 4px rgba(255, 209, 102, 0.8);
    }
    @keyframes sg-pop {
        0% { transform: scale(0.55); }
        60% { transform: scale(1.15); }
        100% { transform: scale(1); }
    }

    .sg-panel {
        background: #170f30;
        border: 1px solid #3a2870;
        border-radius: 14px;
        padding: 12px 14px;
        margin-bottom: 10px;
    }
    .sg-panel h4 { margin: 0 0 6px 0; color: #ffd166; }

    .sg-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-right: 4px;
        margin-bottom: 4px;
    }
    .sg-badge.number { background: #2c1f5c; color: #cbb8ff; }
    .sg-badge.wild { background: #ffd166; color: #3a2200; }
    .sg-badge.extra { background: #06d6a0; color: #06301f; }
    .sg-badge.mult { background: #ef476f; color: #3a0d1e; }
    .sg-badge.coin { background: #ffb703; color: #3a2200; }
    .sg-badge.blocker { background: #3a2870; color: #b7a9e0; }

    div.stButton > button {
        border-radius: 12px;
        font-weight: 700;
        border: none;
    }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(145deg, #ef476f, #ffd166);
        color: #2a0a14;
        font-size: 1.05rem;
        padding: 0.6rem 0;
        box-shadow: 0 4px 18px rgba(239, 71, 111, 0.45);
    }
    </style>
    """, unsafe_allow_html=True)


def render_confetti() -> None:
    """Efek konfeti kanvas ringan, sepenuhnya self-contained (tanpa CDN/internet)."""
    st.components.v1.html("""
    <canvas id="sg-confetti" style="width:100%;height:180px;display:block;"></canvas>
    <script>
    const canvas = document.getElementById('sg-confetti');
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = 180;
    const colors = ['#ffd166', '#ef476f', '#06d6a0', '#118ab2', '#ffffff'];
    let particles = [];
    for (let i = 0; i < 140; i++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: -Math.random() * 100,
            r: Math.random() * 6 + 3,
            c: colors[Math.floor(Math.random() * colors.length)],
            vy: Math.random() * 2 + 2,
            vx: Math.random() * 2 - 1,
            rot: Math.random() * 360,
            vrot: Math.random() * 8 - 4,
        });
    }
    let frame = 0;
    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => {
            p.x += p.vx; p.y += p.vy; p.rot += p.vrot;
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot * Math.PI / 180);
            ctx.fillStyle = p.c;
            ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 0.6);
            ctx.restore();
        });
        frame++;
        if (frame < 90) { requestAnimationFrame(draw); }
    }
    draw();
    </script>
    """, height=180)


def render_board() -> None:
    board = st.session_state.board
    marked = st.session_state.marked
    highlight = set(st.session_state.last_highlight)

    cells_html = ""
    for label in COLUMN_LABELS:
        cells_html += f'<div class="sg-header-cell">{label}</div>'

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            classes = ["sg-cell"]
            if (row, col) == FREE_CELL:
                classes.append("free")
                content = "★"
            else:
                content = str(board[row][col])
                if marked[row][col]:
                    classes.append("marked")
            if (row, col) in highlight:
                classes.append("highlight")
            cells_html += f'<div class="{" ".join(classes)}">{content}</div>'

    st.markdown(f"""
    <div class="sg-board-wrap">
        <div class="sg-grid">{cells_html}</div>
    </div>
    """, unsafe_allow_html=True)


def render_symbol_badge(result: Dict) -> str:
    label = COLUMN_LABELS[result["col"]]
    if result["type"] == "number":
        return f'<span class="sg-badge number">{label}: {result["value"]}</span>'
    icon = BONUS_ICON[result["type"]]
    name = BONUS_NAME[result["type"]]
    return f'<span class="sg-badge {result["type"]}">{label}: {icon} {name}</span>'


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### ⚙️ Pengaturan")

        st.markdown(f"**Tingkat Kesulitan:** {st.session_state.difficulty}")
        if st.session_state.game_status == "setup":
            st.caption("Pilih tingkat kesulitan pada layar utama, lalu klik Mulai Permainan.")

        st.checkbox("🎬 Efek Animasi", key="animations_on")
        st.checkbox("🔊 Suara (placeholder)", key="sound_on",
                    help="Placeholder — belum ada file audio yang digunakan pada aplikasi ini.")

        st.markdown("---")
        st.markdown("### 📊 Statistik")
        st.markdown(f"""
        <div class="sg-panel">
        <b>Skor</b>: {st.session_state.get('score', 0)}<br>
        <b>Multiplier</b>: {st.session_state.get('multiplier', 1.0):.1f}x<br>
        <b>Garis Selesai</b>: {len(st.session_state.get('completed_lines', set()))} / 12<br>
        <b>High Score (sesi ini)</b>: {st.session_state.get('high_score', 0)}
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        with st.expander("❓ How to Play"):
            st.markdown("""
**Tujuan:** Tandai angka pada papan 5x5 untuk melengkapi baris, kolom, atau
diagonal sebelum spin habis.

**Alur permainan:**
1. Pilih tingkat kesulitan, lalu klik **New Game**.
2. Klik **Spin** untuk menghasilkan satu simbol/angka di setiap kolom **S‑P‑I‑N‑G**.
3. Jika angka tersebut ada di papan pada kolom yang sama dan belum ditandai, sel akan otomatis ditandai.
4. Sel tengah papan adalah **Free Space** (★) yang sudah ditandai sejak awal.

**Simbol Bonus:**
- ⭐ **Wild** — menandai satu sel acak yang belum ditandai pada kolom tersebut.
- 🔄 **Extra Spin** — menambah 1 spin ekstra.
- ✨ **Multiplier** — menaikkan pengali skor sebesar +0.5x (maksimum 5.0x).
- 🪙 **Coin Bonus** — memberi skor instan sebesar 50 × multiplier saat ini.
- 🚫 **Blocker/Miss** — tidak memberi efek apa pun.

**Rumus Skor:**
- Baris/Kolom selesai: `100 × multiplier`
- Diagonal selesai: `150 × multiplier`
- Full House (semua 25 sel tertandai): `1000 × multiplier`, permainan langsung berakhir dengan status **Menang**.
- Setiap garis hanya dihitung **satu kali**.

**Permainan berakhir** saat spin habis (status **Game Over**) atau saat Full House tercapai (status **Menang**).
            """)

        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🆕 New Game", use_container_width=True):
                go_to_setup()
                st.rerun()
        with col_b:
            if st.button("♻️ Reset Game", use_container_width=True):
                reset_entire_game()
                st.rerun()


def render_setup_screen() -> None:
    st.markdown('<div class="sg-title">🎰 SpinGrid Quest</div>', unsafe_allow_html=True)
    st.markdown('<div class="sg-subtitle">SLOT REELS MEET BINGO LINES</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="sg-panel">
    Selamat datang di <b>SpinGrid Quest</b> — game orisinal yang memadukan gaya putaran
    slot machine dengan mekanisme melengkapi garis ala bingo. Tandai baris, kolom, atau
    diagonal pada papan 5×5 sebelum kehabisan spin, kumpulkan simbol bonus, dan kejar skor tertinggimu!
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Pilih Tingkat Kesulitan")
    diff = st.radio(
        "Tingkat Kesulitan",
        options=list(DIFFICULTY_SETTINGS.keys()),
        index=list(DIFFICULTY_SETTINGS.keys()).index(st.session_state.difficulty),
        horizontal=True,
        label_visibility="collapsed",
        key="difficulty_radio",
    )
    settings = DIFFICULTY_SETTINGS[diff]
    st.caption(f"Jumlah spin: **{settings['spins']}** • Peluang simbol bonus per kolom: **{int(settings['bonus_prob']*100)}%**")

    if st.session_state.high_score > 0:
        st.info(f"🏆 High Score sesi ini: **{st.session_state.high_score}**")

    if st.button("▶️ Mulai Permainan", type="primary", use_container_width=True):
        start_new_round(diff)
        st.rerun()


def render_playing_screen() -> None:
    st.markdown('<div class="sg-title">🎰 SpinGrid Quest</div>', unsafe_allow_html=True)
    st.markdown('<div class="sg-subtitle">SLOT REELS MEET BINGO LINES</div>', unsafe_allow_html=True)

    top_l, top_r = st.columns([3, 2])
    with top_l:
        progress_ratio = st.session_state.spins_remaining / max(st.session_state.spins_total, 1)
        st.progress(min(1.0, max(0.0, progress_ratio)), text=f"Spin tersisa: {st.session_state.spins_remaining} / {st.session_state.spins_total}")
    with top_r:
        st.markdown(
            f"**Skor:** {st.session_state.score} &nbsp;|&nbsp; "
            f"**Multiplier:** {st.session_state.multiplier:.1f}x &nbsp;|&nbsp; "
            f"**Garis:** {len(st.session_state.completed_lines)}/12"
        )

    board_col, side_col = st.columns([3, 2])

    with board_col:
        render_board()
        st.write("")
        spin_disabled = st.session_state.spins_remaining <= 0
        if st.button("🎲 SPIN", type="primary", use_container_width=True, disabled=spin_disabled):
            if st.session_state.animations_on:
                with st.spinner("Reel berputar..."):
                    time.sleep(0.35)
            perform_spin()
            st.rerun()

    with side_col:
        st.markdown("#### 🕘 Riwayat Spin")
        if not st.session_state.spin_history:
            st.caption("Belum ada spin pada ronde ini.")
        else:
            for entry in st.session_state.spin_history:
                badges = "".join(render_symbol_badge(r) for r in entry["results"])
                extra = f' • +{entry["lines_gained"]} garis' if entry["lines_gained"] else ""
                st.markdown(f"""
                <div class="sg-panel">
                <b>Spin #{entry['spin_no']}</b>{extra}<br>{badges}
                </div>
                """, unsafe_allow_html=True)


def render_end_screen() -> None:
    won = st.session_state.game_status == "won"
    st.markdown('<div class="sg-title">🎰 SpinGrid Quest</div>', unsafe_allow_html=True)

    if won:
        st.markdown('<div class="sg-subtitle">FULL HOUSE — KAMU MENANG!</div>', unsafe_allow_html=True)
        if st.session_state.animations_on:
            render_confetti()
        st.success("🎉 Selamat! Kamu berhasil menandai seluruh papan (Full House)!")
    else:
        st.markdown('<div class="sg-subtitle">GAME OVER</div>', unsafe_allow_html=True)
        st.warning("Spin telah habis. Coba lagi untuk mengejar skor yang lebih tinggi!")

    render_board()

    st.markdown(f"""
    <div class="sg-panel">
    <h4>Ringkasan Ronde</h4>
    <b>Skor Akhir:</b> {st.session_state.score}<br>
    <b>Multiplier Akhir:</b> {st.session_state.multiplier:.1f}x<br>
    <b>Garis Terselesaikan:</b> {len(st.session_state.completed_lines)} / 12<br>
    <b>Total Spin Digunakan:</b> {st.session_state.spin_count}<br>
    <b>High Score Sesi:</b> {st.session_state.high_score}
    </div>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔁 Play Again", type="primary", use_container_width=True):
            start_new_round(st.session_state.difficulty)
            st.rerun()
    with col_b:
        if st.button("🆕 Pilih Tingkat Kesulitan Lain", use_container_width=True):
            go_to_setup()
            st.rerun()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main() -> None:
    st.set_page_config(page_title="SpinGrid Quest", page_icon="🎰", layout="wide")
    init_app_state()
    inject_css()
    render_sidebar()

    status = st.session_state.game_status
    if status == "setup":
        render_setup_screen()
    elif status == "playing":
        render_playing_screen()
    else:  # "over" or "won"
        render_end_screen()


if __name__ == "__main__":
    main()
