import streamlit as st
import random

# Constants
RANGES = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]

def init_game():
    st.session_state.grid = []
    for r in range(5):
        st.session_state.grid.append([{'val': 0, 'marked': False} for _ in range(5)])
    
    for c in range(5):
        nums = random.sample(range(RANGES[c][0], RANGES[c][1] + 1), 5)
        for r in range(5):
            st.session_state.grid[r][c]['val'] = nums[r]
            
    st.session_state.score = 0
    st.session_state.spins_left = 20
    st.session_state.slots = ["-"] * 5
    st.session_state.pending_jokers = []
    st.session_state.scored_lines = set()
    st.session_state.log = ["Selamat datang di Slingo Deluxe! Klik SPIN untuk mulai."]
    st.session_state.game_over = False

def log(msg):
    st.session_state.log.insert(0, msg)
    if len(st.session_state.log) > 10:
        st.session_state.log.pop()

def check_lines():
    lines = []
    for r in range(5): lines.append((f'R{r}', [(r, c) for c in range(5)]))
    for c in range(5): lines.append((f'C{c}', [(r, c) for r in range(5)]))
    lines.append(('D1', [(i, i) for i in range(5)]))
    lines.append(('D2', [(i, 4-i) for i in range(5)]))
    
    new_lines = 0
    for name, coords in lines:
        if name not in st.session_state.scored_lines:
            if all(st.session_state.grid[r][c]['marked'] for r, c in coords):
                st.session_state.scored_lines.add(name)
                new_lines += 1
                
    if new_lines > 0:
        pts = new_lines * 1000
        st.session_state.score += pts
        log(f"⭐ SLINGO! {new_lines} baris selesai. +{pts} poin!")
        
    if len(st.session_state.scored_lines) == 12 and 'FullHouse' not in st.session_state.scored_lines:
        st.session_state.scored_lines.add('FullHouse')
        st.session_state.score += 5000
        log("🌟 FULL HOUSE! Papan bersih! +5000 poin! 🌟")
        st.session_state.game_over = True

def spin():
    if st.session_state.spins_left <= 0: return
    st.session_state.spins_left -= 1
    st.session_state.slots = []
    
    for c in range(5):
        roll = random.random()
        # Probabilitas spawn item
        if roll < 0.05: res = 'Joker'
        elif roll < 0.07: res = 'Super Joker'
        elif roll < 0.12: res = 'Devil'
        elif roll < 0.17: res = 'Coin'
        elif roll < 0.20: res = 'Free Spin'
        else: res = random.randint(RANGES[c][0], RANGES[c][1])
        st.session_state.slots.append(res)
        
    # Proses hasil slot
    for c, res in enumerate(st.session_state.slots):
        if isinstance(res, int):
            for r in range(5):
                if st.session_state.grid[r][c]['val'] == res and not st.session_state.grid[r][c]['marked']:
                    st.session_state.grid[r][c]['marked'] = True
                    st.session_state.score += 200
                    log(f"Cocok {res}! +200 poin.")
                    break
        elif res == 'Coin':
            st.session_state.score += 1000
            log("💰 Gold Coin! +1000 poin.")
        elif res == 'Free Spin':
            st.session_state.spins_left += 1
            log("🔄 Free Spin! +1 Putaran.")
        elif res == 'Devil':
            if random.random() < 0.5:
                log("😈 Devil muncul... tapi 👼 Cherub menyelamatkanmu!")
                st.session_state.slots[c] = 'Cherub'
            else:
                st.session_state.score //= 2
                log("😈 Devil memotong skormu jadi setengah!")
        elif res == 'Joker':
            st.session_state.pending_jokers.append({'type': 'Joker', 'col': c})
        elif res == 'Super Joker':
            st.session_state.pending_jokers.append({'type': 'Super Joker', 'col': c})
            
    check_lines()
    if st.session_state.spins_left <= 0 and not st.session_state.pending_jokers:
        st.session_state.game_over = True

def mark_cell(r, c):
    if not st.session_state.pending_jokers: return
    st.session_state.grid[r][c]['marked'] = True
    st.session_state.score += 200
    joker = st.session_state.pending_jokers.pop(0)
    log(f"Pakai {joker['type']} di {st.session_state.grid[r][c]['val']}! +200 poin.")
    check_lines()

# === UI STREAMLIT ===
st.set_page_config(page_title="Slingo Deluxe Clone", layout="centered")

st.markdown("""
<style>
    .title {text-align: center; color: #ffeb3b; text-shadow: 2px 2px #f44336; font-family: 'Arial Black', sans-serif;}
    .slot-box {text-align: center; font-size: 24px; font-weight: bold; background: linear-gradient(145deg, #ffd700, #ff8c00); color: #000; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);}
    .log-box {background-color: #2b2b2b; color: #4caf50; padding: 15px; border-radius: 8px; font-family: monospace; height: 180px; overflow-y: auto; box-shadow: inset 0px 0px 10px #000;}
    div.stButton > button {height: 60px; font-size: 18px; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='title'>🎰 SLINGO DELUXE 🎰</h1>", unsafe_allow_html=True)

if 'grid' not in st.session_state:
    init_game()

col1, col2, col3 = st.columns(3)
col1.metric("Skor", st.session_state.score)
col2.metric("Sisa Putaran", st.session_state.spins_left)
col3.metric("Slingo", len([x for x in st.session_state.scored_lines if x != 'FullHouse']))

active_joker = None
if st.session_state.pending_jokers:
    active_joker = st.session_state.pending_jokers[0]
    msg = f"🎯 AKSI DIBUTUHKAN: Pilih angka untuk {active_joker['type']}!"
    if active_joker['type'] == 'Joker': msg += f" (Di Kolom {active_joker['col'] + 1})"
    st.warning(msg)

st.markdown("### Papan Slingo")
for r in range(5):
    cols = st.columns(5)
    for c in range(5):
        cell = st.session_state.grid[r][c]
        label = str(cell['val'])
        is_clickable = False
        
        if cell['marked']:
            label = "⭐"
        else:
            if active_joker:
                if active_joker['type'] == 'Super Joker':
                    is_clickable = True; label = f"🎯 {cell['val']}"
                elif active_joker['type'] == 'Joker' and active_joker['col'] == c:
                    is_clickable = True; label = f"🎯 {cell['val']}"
                    
        with cols[c]:
            if cell['marked'] or not is_clickable:
                st.button(label, key=f"c_{r}_{c}", disabled=True)
            else:
                if st.button(label, key=f"c_{r}_{c}"):
                    mark_cell(r, c)
                    st.rerun()

st.divider()

st.markdown("### Mesin Slot")
slot_cols = st.columns(5)
for c in range(5):
    res = st.session_state.slots[c]
    disp = str(res)
    if res == 'Joker': disp = '🃏'
    elif res == 'Super Joker': disp = '🌠'
    elif res == 'Devil': disp = '😈'
    elif res == 'Cherub': disp = '👼'
    elif res == 'Coin': disp = '💰'
    elif res == 'Free Spin': disp = '🔄'
    with slot_cols[c]:
        st.markdown(f"<div class='slot-box'>{disp}</div>", unsafe_allow_html=True)

st.write("")
b1, b2 = st.columns(2)
with b1:
    if st.button("🎲 SPIN", use_container_width=True, disabled=(active_joker is not None) or st.session_state.game_over, type="primary"):
        spin()
        st.rerun()
with b2:
    if st.button("🔄 RESTART", use_container_width=True):
        init_game()
        st.rerun()

if st.session_state.game_over:
    st.error(f"Permainan Selesai! Skor Akhir: {st.session_state.score}")
    if len(st.session_state.scored_lines) >= 12: st.balloons()

st.markdown("### Riwayat Permainan")
st.markdown("<div class='log-box'>" + "<br>".join(st.session_state.log) + "</div>", unsafe_allow_html=True)
