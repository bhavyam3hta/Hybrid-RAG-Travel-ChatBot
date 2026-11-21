"""
visualize_graph.py - Cartoon Knowledge Graph Visualizer for Vietnam Travel Chatbot
Fetches nodes & relationships from Neo4j Aura and generates an interactive,
cartoon-styled, neo-brutalist HTML visualization (neo4j_viz.html).
"""

import json
from neo4j import GraphDatabase
import config

def clean_text(val):
    if not val:
        return ""
    val = str(val)
    # Replace unicode dashes with standard hyphens
    for d in ["\u2014", "\u2013", "\u2012", "\u2015"]:
        val = val.replace(d, " - ")
    # Replace smart quotes with standard ASCII quotes
    for q in ["\u2018", "\u2019"]:
        val = val.replace(q, "'")
    for q in ["\u201c", "\u201d"]:
        val = val.replace(q, '"')
    val = val.replace("\u2026", "...")
    return val.strip()


def fetch_graph():
    print("🔌 Connecting to Neo4j to fetch graph data...")
    driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
    
    with driver.session() as session:
        nodes_res = session.run("""
            MATCH (n:Entity)
            RETURN n.id AS id, labels(n) AS labels, properties(n) AS props
        """).data()

        rels_res = session.run("""
            MATCH (a:Entity)-[r]->(b:Entity)
            RETURN a.id AS source, b.id AS target, type(r) AS rel
        """).data()
        
    driver.close()
    print(f"✅ Fetched {len(nodes_res)} nodes and {len(rels_res)} relationships.")
    return nodes_res, rels_res


def generate_html(nodes_raw, rels_raw, output_path="neo4j_viz.html"):
    nodes_data = []
    category_counts = {"city": 0, "attraction": 0, "hotel": 0, "activity": 0}

    # Style mapping by category
    category_styles = {
        "city": {
            "emoji": "🏙️",
            "bg": "#FFDD00",
            "border": "#18181b",
            "size": 42,
            "font_size": 16,
            "border_width": 4,
            "badge_color": "#FFDD00"
        },
        "attraction": {
            "emoji": "📍",
            "bg": "#FF5B84",
            "border": "#18181b",
            "size": 24,
            "font_size": 12,
            "border_width": 3,
            "badge_color": "#FF5B84"
        },
        "hotel": {
            "emoji": "🏨",
            "bg": "#00F0FF",
            "border": "#18181b",
            "size": 19,
            "font_size": 11,
            "border_width": 2.5,
            "badge_color": "#00F0FF"
        },
        "activity": {
            "emoji": "🏄",
            "bg": "#00E599",
            "border": "#18181b",
            "size": 19,
            "font_size": 11,
            "border_width": 2.5,
            "badge_color": "#00E599"
        }
    }

    cities_list = []

    for item in nodes_raw:
        nid = clean_text(item["id"])
        labels = [clean_text(l) for l in item.get("labels", [])]
        props = item.get("props", {})

        ntype = clean_text(props.get("type", "")).lower()
        if "city" in ntype or "City" in labels:
            cat = "city"
        elif "attraction" in ntype or "Attraction" in labels:
            cat = "attraction"
        elif "hotel" in ntype or "Hotel" in labels:
            cat = "hotel"
        elif "activity" in ntype or "Activity" in labels:
            cat = "activity"
        else:
            cat = "attraction"

        category_counts[cat] += 1
        cfg = category_styles[cat]

        raw_name = clean_text(props.get("name", nid))
        city = clean_text(props.get("city", ""))
        region = clean_text(props.get("region", ""))
        desc = clean_text(props.get("description", ""))
        best_time = clean_text(props.get("best_time_to_visit", ""))
        tags = [clean_text(t) for t in props.get("tags", [])]

        if cat == "city":
            cities_list.append({"id": nid, "name": raw_name})

        display_label = f"{cfg['emoji']} {raw_name}"

        node_obj = {
            "id": nid,
            "label": display_label,
            "name": raw_name,
            "category": cat,
            "type": cat.title(),
            "city": city or (region if cat == "city" else ""),
            "region": region,
            "description": desc,
            "best_time": best_time,
            "tags": tags,
            "shape": "dot",
            "size": cfg["size"],
            "borderWidth": cfg["border_width"],
            "borderWidthSelected": cfg["border_width"] + 2,
            "color": {
                "background": cfg["bg"],
                "border": cfg["border"],
                "highlight": {
                    "background": "#FFFFFF",
                    "border": "#18181b"
                },
                "hover": {
                    "background": cfg["bg"],
                    "border": "#000000"
                }
            },
            "font": {
                "face": "Fredoka, sans-serif",
                "size": cfg["font_size"],
                "color": "#18181b",
                "strokeWidth": 3,
                "strokeColor": "#FFFFFF"
            },
            "shadow": {
                "enabled": True,
                "color": "#18181b",
                "size": 8,
                "x": 4,
                "y": 4
            }
        }
        nodes_data.append(node_obj)

    # Edge styling
    edges_data = []
    for r in rels_raw:
        src = clean_text(r["source"])
        tgt = clean_text(r["target"])
        rel_type = clean_text(r["rel"])

        if rel_type == "Connected_To":
            edge_obj = {
                "from": src,
                "to": tgt,
                "label": "route",
                "color": {
                    "color": "#9333EA",
                    "highlight": "#FFDD00",
                    "hover": "#FF5B84"
                },
                "width": 4.5,
                "dashes": [6, 6],
                "arrows": {"to": {"enabled": True, "scaleFactor": 1.1}},
                "title": f"Inter-city Route: {src} -> {tgt}",
                "rel": "Connected_To"
            }
        elif rel_type == "Located_In":
            edge_obj = {
                "from": src,
                "to": tgt,
                "color": {
                    "color": "rgba(255, 91, 132, 0.45)",
                    "highlight": "#FF5B84",
                    "hover": "#FFDD00"
                },
                "width": 2,
                "arrows": {"to": {"enabled": True, "scaleFactor": 0.8}},
                "title": f"Located In: {src} -> {tgt}",
                "rel": "Located_In"
            }
        else: # Available_In
            edge_obj = {
                "from": src,
                "to": tgt,
                "color": {
                    "color": "rgba(0, 229, 153, 0.45)",
                    "highlight": "#00E599",
                    "hover": "#FFDD00"
                },
                "width": 2,
                "arrows": {"to": {"enabled": True, "scaleFactor": 0.8}},
                "title": f"Available In: {src} -> {tgt}",
                "rel": "Available_In"
            }
        edges_data.append(edge_obj)

    cities_list.sort(key=lambda x: x["name"])

    nodes_json = json.dumps(nodes_data)
    edges_json = json.dumps(edges_data)
    cities_json = json.dumps(cities_list)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Vietnam Travel Explorer - Cartoon Knowledge Graph</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;700;800&display=swap" rel="stylesheet">
  <script src="/lib/vis-9.1.2/vis-network.min.js"></script>
  <link rel="stylesheet" href="/lib/vis-9.1.2/vis-network.css" />
  <script>
    if (typeof vis === 'undefined') {{
      document.write('<script src="lib/vis-9.1.2/vis-network.min.js"><\\/script>');
    }}
  </script>
  <script>
    if (typeof vis === 'undefined') {{
      document.write('<script src="https://unpkg.com/vis-network@9.1.2/standalone/umd/vis-network.min.js"><\\/script>');
    }}
  </script>

  <style>
    :root {{
      --bg: #FFFDF5;
      --black: #18181b;
      --yellow: #FFDD00;
      --pink: #FF5B84;
      --cyan: #00F0FF;
      --green: #00E599;
      --purple: #9333EA;
      --purple-light: #C084FC;
      --card-bg: #FFFFFF;
      --shadow-sm: 3px 3px 0px var(--black);
      --shadow: 5px 5px 0px var(--black);
      --shadow-lg: 8px 8px 0px var(--black);
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: 'Fredoka', 'Plus Jakarta Sans', sans-serif;
      background-color: var(--bg);
      background-image: radial-gradient(var(--black) 1px, transparent 1px);
      background-size: 24px 24px;
      color: var(--black);
      overflow: hidden;
      width: 100vw;
      height: 100vh;
      position: relative;
    }}

    /* NETWORK CONTAINER */
    #network-canvas {{
      width: 100vw;
      height: 100vh;
      position: absolute;
      top: 0;
      left: 0;
      z-index: 1;
    }}

    /* TOP CONTROLS HUD */
    .top-hud {{
      position: absolute;
      top: 16px;
      left: 16px;
      right: 16px;
      z-index: 10;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      pointer-events: none;
    }}

    .hud-group {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      pointer-events: auto;
    }}

    /* BRAND CARD */
    .brand-card {{
      background: var(--yellow);
      border: 3.5px solid var(--black);
      border-radius: 18px;
      padding: 10px 18px;
      box-shadow: var(--shadow);
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .brand-card h1 {{
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: -0.3px;
    }}

    .brand-card .subtitle {{
      font-size: 0.85rem;
      font-weight: 600;
      opacity: 0.85;
    }}

    /* BUTTONS */
    .cartoon-btn {{
      font-family: inherit;
      font-size: 0.95rem;
      font-weight: 700;
      padding: 10px 16px;
      border: 3px solid var(--black);
      border-radius: 14px;
      background: #FFFFFF;
      color: var(--black);
      cursor: pointer;
      box-shadow: var(--shadow-sm);
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      text-decoration: none;
      user-select: none;
    }}

    .cartoon-btn:hover {{
      transform: translate(-2px, -2px);
      box-shadow: 5px 5px 0px var(--black);
    }}

    .cartoon-btn:active {{
      transform: translate(2px, 2px);
      box-shadow: 1px 1px 0px var(--black);
    }}

    .btn-back {{
      background: var(--yellow);
    }}

    .btn-cyan {{
      background: var(--cyan);
    }}

    .btn-pink {{
      background: var(--pink);
      color: #fff;
    }}

    .btn-green {{
      background: var(--green);
    }}

    .btn-purple {{
      background: var(--purple);
      color: #fff;
    }}

    /* SEARCH WRAPPER */
    .search-box {{
      position: relative;
      width: 260px;
      pointer-events: auto;
    }}

    .search-input {{
      width: 100%;
      padding: 10px 14px;
      font-family: inherit;
      font-size: 0.95rem;
      font-weight: 600;
      border: 3px solid var(--black);
      border-radius: 14px;
      background: #FFFFFF;
      box-shadow: var(--shadow-sm);
      outline: none;
      transition: all 0.2s;
    }}

    .search-input:focus {{
      box-shadow: 5px 5px 0px var(--black);
      transform: translateY(-1px);
    }}

    .search-results {{
      position: absolute;
      top: calc(100% + 6px);
      left: 0;
      right: 0;
      background: #FFFFFF;
      border: 3px solid var(--black);
      border-radius: 14px;
      box-shadow: var(--shadow);
      max-height: 240px;
      overflow-y: auto;
      display: none;
      z-index: 100;
    }}

    .search-item {{
      padding: 8px 12px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      border-bottom: 2px dashed #eee;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .search-item:hover {{
      background: var(--yellow);
    }}

    /* FILTER PILLS BAR */
    .filter-bar {{
      position: absolute;
      top: 86px;
      left: 16px;
      z-index: 10;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      pointer-events: auto;
    }}

    .filter-pill {{
      background: #FFFFFF;
      border: 2.5px solid var(--black);
      border-radius: 999px;
      padding: 6px 14px;
      font-size: 0.85rem;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 2px 2px 0px var(--black);
      transition: all 0.15s;
      user-select: none;
    }}

    .filter-pill:hover, .filter-pill.active {{
      transform: translate(-2px, -2px);
      box-shadow: 4px 4px 0px var(--black);
    }}

    .filter-pill.active.pill-all {{ background: var(--black); color: #fff; }}
    .filter-pill.active.pill-city {{ background: var(--yellow); }}
    .filter-pill.active.pill-attraction {{ background: var(--pink); color: #fff; }}
    .filter-pill.active.pill-hotel {{ background: var(--cyan); }}
    .filter-pill.active.pill-activity {{ background: var(--green); }}

    /* CITY DROPDOWN */
    .city-select {{
      font-family: inherit;
      font-size: 0.9rem;
      font-weight: 700;
      padding: 8px 14px;
      border: 2.5px solid var(--black);
      border-radius: 14px;
      background: #FFFFFF;
      box-shadow: var(--shadow-sm);
      cursor: pointer;
      outline: none;
    }}

    /* LEGEND BOX */
    .legend-card {{
      position: absolute;
      bottom: 20px;
      left: 16px;
      z-index: 10;
      background: #FFFFFF;
      border: 3.5px solid var(--black);
      border-radius: 18px;
      padding: 14px 18px;
      box-shadow: var(--shadow);
      max-width: 280px;
      pointer-events: auto;
    }}

    .legend-title {{
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .legend-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 5px;
    }}

    .legend-dot {{
      width: 14px;
      height: 14px;
      border-radius: 50%;
      border: 2px solid var(--black);
      display: inline-block;
    }}

    .legend-dot.city {{ background: var(--yellow); width: 16px; height: 16px; }}
    .legend-dot.attraction {{ background: var(--pink); }}
    .legend-dot.hotel {{ background: var(--cyan); }}
    .legend-dot.activity {{ background: var(--green); }}

    .legend-line {{
      width: 18px;
      height: 4px;
      border: 1px solid var(--black);
      display: inline-block;
      border-radius: 2px;
    }}
    .legend-line.route {{ background: var(--purple); }}
    .legend-line.located {{ background: var(--pink); }}

    /* NODE DETAILS DRAWER */
    .drawer-card {{
      position: absolute;
      top: 90px;
      right: 16px;
      width: 360px;
      max-width: calc(100vw - 32px);
      max-height: calc(100vh - 120px);
      background: #FFFDF0;
      border: 4px solid var(--black);
      border-radius: 24px;
      box-shadow: var(--shadow-lg);
      padding: 22px;
      z-index: 20;
      overflow-y: auto;
      display: none;
      animation: popIn 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}

    @keyframes popIn {{
      0% {{ transform: scale(0.85) translateY(20px); opacity: 0; }}
      100% {{ transform: scale(1) translateY(0); opacity: 1; }}
    }}

    .drawer-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 3px dashed var(--black);
    }}

    .drawer-title {{
      font-size: 1.35rem;
      font-weight: 700;
      line-height: 1.2;
    }}

    .drawer-close {{
      background: var(--pink);
      color: #fff;
      border: 2px solid var(--black);
      border-radius: 50%;
      width: 32px;
      height: 32px;
      font-size: 1rem;
      font-weight: 800;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      box-shadow: 2px 2px 0px var(--black);
      flex-shrink: 0;
    }}

    .drawer-close:hover {{
      transform: scale(1.1);
    }}

    .drawer-badge {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 10px;
      font-size: 0.8rem;
      font-weight: 700;
      border: 2px solid var(--black);
      border-radius: 999px;
      margin-bottom: 10px;
      box-shadow: 2px 2px 0px var(--black);
    }}

    .drawer-location {{
      font-size: 0.95rem;
      font-weight: 700;
      color: #444;
      margin-bottom: 8px;
    }}

    .drawer-desc {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 0.92rem;
      line-height: 1.55;
      color: #222;
      margin-bottom: 14px;
    }}

    .drawer-tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 14px;
    }}

    .drawer-tag {{
      background: var(--yellow);
      border: 1.5px solid var(--black);
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 700;
      padding: 2px 8px;
    }}

    .neighbors-box {{
      margin-top: 14px;
      padding-top: 12px;
      border-top: 2px dashed #ddd;
    }}

    .neighbors-title {{
      font-size: 0.95rem;
      font-weight: 700;
      margin-bottom: 8px;
    }}

    .neighbor-pill {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #FFFFFF;
      border: 2px solid var(--black);
      border-radius: 12px;
      padding: 4px 10px;
      font-size: 0.82rem;
      font-weight: 700;
      margin: 3px 2px;
      cursor: pointer;
      box-shadow: 2px 2px 0px var(--black);
      transition: all 0.15s;
    }}

    .neighbor-pill:hover {{
      background: var(--cyan);
      transform: translateY(-2px);
    }}

    .cta-btn {{
      margin-top: 16px;
      width: 100%;
      background: var(--yellow);
      color: var(--black);
      font-family: inherit;
      font-size: 1rem;
      font-weight: 800;
      padding: 12px;
      border: 3px solid var(--black);
      border-radius: 16px;
      box-shadow: var(--shadow);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      text-decoration: none;
      transition: all 0.15s ease;
    }}

    .cta-btn:hover {{
      transform: translate(-2px, -2px);
      box-shadow: 6px 6px 0px var(--black);
      background: #FFE600;
    }}

    /* CARTOON LOADING MODAL WITH PERCENTAGE */
    #loadingScreen {{
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(255, 253, 245, 0.94);
      background-image: radial-gradient(var(--black) 1.5px, transparent 1.5px);
      background-size: 24px 24px;
      backdrop-filter: blur(6px);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      transition: opacity 0.35s ease, visibility 0.35s ease;
    }}

    .loading-card {{
      background: var(--yellow);
      border: 4px solid var(--black);
      border-radius: 28px;
      padding: 32px 36px;
      box-shadow: var(--shadow-lg);
      text-align: center;
      max-width: 460px;
      width: 90%;
      position: relative;
      animation: popCard 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}

    @keyframes popCard {{
      0% {{ transform: scale(0.85); opacity: 0; }}
      100% {{ transform: scale(1); opacity: 1; }}
    }}

    .loading-icon {{
      font-size: 3.2rem;
      margin-bottom: 8px;
      display: inline-block;
      animation: wiggle 1s ease-in-out infinite;
    }}

    @keyframes wiggle {{
      0%, 100% {{ transform: rotate(0deg) scale(1); }}
      25% {{ transform: rotate(-8deg) scale(1.05); }}
      75% {{ transform: rotate(8deg) scale(1.05); }}
    }}

    .loading-title {{
      font-size: 1.55rem;
      font-weight: 800;
      letter-spacing: -0.4px;
      margin-bottom: 4px;
    }}

    .loading-estimate {{
      font-size: 0.9rem;
      font-weight: 600;
      color: #333;
      margin-bottom: 18px;
    }}

    .progress-meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }}

    .progress-label {{
      font-size: 0.9rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    .progress-percent {{
      font-size: 1.5rem;
      font-weight: 800;
      color: var(--black);
      background: #FFFFFF;
      border: 2px solid var(--black);
      border-radius: 10px;
      padding: 2px 10px;
      box-shadow: var(--shadow-sm);
    }}

    .progress-track {{
      background: #FFFFFF;
      border: 3.5px solid var(--black);
      border-radius: 999px;
      height: 28px;
      width: 100%;
      overflow: hidden;
      box-shadow: inset 2px 2px 0px rgba(0,0,0,0.12);
      position: relative;
      margin-bottom: 14px;
    }}

    .progress-fill {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--pink), var(--green));
      background-size: 32px 32px;
      background-image: linear-gradient(
        45deg,
        rgba(255, 255, 255, 0.3) 25%,
        transparent 25%,
        transparent 50%,
        rgba(255, 255, 255, 0.3) 50%,
        rgba(255, 255, 255, 0.3) 75%,
        transparent 75%,
        transparent
      );
      animation: candyStripes 1s linear infinite;
      border-radius: 999px;
      transition: width 0.12s ease-out;
    }}

    @keyframes candyStripes {{
      0% {{ background-position: 0 0; }}
      100% {{ background-position: 32px 0; }}
    }}

    .loading-status-pill {{
      display: inline-block;
      background: #FFFFFF;
      border: 2px solid var(--black);
      border-radius: 12px;
      padding: 6px 14px;
      font-size: 0.88rem;
      font-weight: 700;
      box-shadow: var(--shadow-sm);
      color: #18181b;
    }}
  </style>
</head>
<body>

  <!-- CARTOON LOADING OVERLAY WITH REALTIME PERCENTAGE -->
  <div id="loadingScreen">
    <div class="loading-card">
      <div class="loading-icon">🛵💨</div>
      <h2 class="loading-title">Spawning Travel Galaxy</h2>
      <div class="loading-estimate">⏱️ Estimated load time: ~2 seconds</div>

      <div class="progress-meta">
        <span class="progress-label">Graph Physics Simulation</span>
        <span class="progress-percent" id="progressPercent">0%</span>
      </div>

      <div class="progress-track">
        <div class="progress-fill" id="progressFill"></div>
      </div>

      <div class="loading-status-pill" id="loadingStatus">
        Initializing 360 destinations and 370 connections...
      </div>
    </div>
  </div>

  <!-- NETWORK CANVAS -->
  <div id="network-canvas"></div>

  <!-- TOP BAR HUD -->
  <div class="top-hud">
    <div class="hud-group">
      <div class="brand-card">
        <span style="font-size: 1.5rem;">🌴</span>
        <div>
          <h1>Vietnam Knowledge Graph</h1>
          <div class="subtitle">360 Nodes • 370 Relationships • Spring Physics</div>
        </div>
      </div>
      <a href="/" class="cartoon-btn btn-back" id="btnBackToChat" onclick="returnToChatbot(event)">
        <span>⬅️ Chatbot</span>
      </a>
    </div>

    <div class="hud-group">
      <!-- LIVE SEARCH -->
      <div class="search-box">
        <input 
          type="text" 
          id="searchInput" 
          class="search-input" 
          placeholder="🔍 Search node (e.g. Hoi An)..." 
          autocomplete="off"
        />
        <div class="search-results" id="searchResults"></div>
      </div>

      <!-- CITY JUMP -->
      <select id="citySelect" class="city-select">
        <option value="">🎯 Jump to City Hub...</option>
      </select>

      <!-- PHYSICS / CONTROLS -->
      <button class="cartoon-btn btn-cyan" id="btnFit" title="Fit Entire Graph">
        <span>🎯 Fit View</span>
      </button>
      <button class="cartoon-btn btn-purple" id="btnPhysics" title="Pause/Resume Physics">
        <span id="physicsIcon">⏸️ Freeze</span>
      </button>
      <button class="cartoon-btn btn-pink" id="btnJelly" title="Shake the Graph!">
        <span>🔀 Jelly Wobble</span>
      </button>
    </div>
  </div>

  <!-- FILTER PILLS -->
  <div class="filter-bar">
    <span class="filter-pill active pill-all" data-category="all">🌟 All ({len(nodes_data)})</span>
    <span class="filter-pill pill-city" data-category="city">🏙️ Cities ({category_counts['city']})</span>
    <span class="filter-pill pill-attraction" data-category="attraction">📍 Attractions ({category_counts['attraction']})</span>
    <span class="filter-pill pill-hotel" data-category="hotel">🏨 Hotels ({category_counts['hotel']})</span>
    <span class="filter-pill pill-activity" data-category="activity">🏄 Activities ({category_counts['activity']})</span>
  </div>

  <!-- LEGEND -->
  <div class="legend-card">
    <div class="legend-title">
      <span>🎨 Graph Legend</span>
      <span style="font-size:0.8rem; font-weight:600; opacity:0.7;">Click node to inspect</span>
    </div>
    <div class="legend-row">
      <span class="legend-dot city"></span>
      <span>City Hubs (10 main destinations)</span>
    </div>
    <div class="legend-row">
      <span class="legend-dot attraction"></span>
      <span>Attractions & Sights (150)</span>
    </div>
    <div class="legend-row">
      <span class="legend-dot hotel"></span>
      <span>Hotels & Stays (100)</span>
    </div>
    <div class="legend-row">
      <span class="legend-dot activity"></span>
      <span>Activities & Food (100)</span>
    </div>
    <div class="legend-row" style="margin-top: 8px;">
      <span class="legend-line route"></span>
      <span>Inter-city Travel Routes</span>
    </div>
    <div class="legend-row">
      <span class="legend-line located"></span>
      <span>Locations & Activities in City</span>
    </div>
  </div>

  <!-- NODE DETAILS DRAWER -->
  <div class="drawer-card" id="drawerCard">
    <div class="drawer-header">
      <div>
        <div class="drawer-badge" id="drawerBadge">City</div>
        <h2 class="drawer-title" id="drawerTitle">Hanoi</h2>
      </div>
      <button class="drawer-close" id="drawerClose">✖</button>
    </div>
    <div class="drawer-location" id="drawerLocation">📍 Northern Vietnam</div>
    <div class="drawer-desc" id="drawerDesc">Description goes here...</div>
    <div class="drawer-tags" id="drawerTags"></div>
    <div class="neighbors-box">
      <div class="neighbors-title">🔗 Connected in Graph (<span id="neighborsCount">0</span>):</div>
      <div id="neighborsList"></div>
    </div>
    <a href="#" class="cta-btn" id="drawerChatBtn" target="_blank">
      <span>💬 Ask Chatbot About This Place 🚀</span>
    </a>
  </div>

  <script>
    const rawNodes = {nodes_json};
    const rawEdges = {edges_json};
    const rawCities = {cities_json};

    // Populate City Dropdown
    const citySelect = document.getElementById('citySelect');
    rawCities.forEach(c => {{
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = '🏙️ ' + c.name;
      citySelect.appendChild(opt);
    }});

    // Build Vis.js DataSets
    const nodesDataSet = new vis.DataSet(rawNodes);
    const edgesDataSet = new vis.DataSet(rawEdges);

    const container = document.getElementById('network-canvas');
    const data = {{ nodes: nodesDataSet, edges: edgesDataSet }};

    const options = {{
      nodes: {{
        shape: 'dot',
        font: {{
          face: 'Fredoka, sans-serif',
          color: '#18181b',
          strokeWidth: 3,
          strokeColor: '#FFFFFF',
          size: 13
        }},
        shadow: {{
          enabled: true,
          color: '#18181b',
          size: 8,
          x: 4,
          y: 4
        }}
      }},
      edges: {{
        arrows: {{
          to: {{ enabled: true, scaleFactor: 0.9 }}
        }},
        smooth: {{
          type: 'continuous',
          roundness: 0.25
        }},
        shadow: {{
          enabled: true,
          color: 'rgba(24, 24, 27, 0.3)',
          size: 4,
          x: 2,
          y: 2
        }}
      }},
      physics: {{
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {{
          gravitationalConstant: -130,
          centralGravity: 0.025,
          springLength: 95,
          springConstant: 0.08,
          damping: 0.42,
          avoidOverlap: 0.75
        }},
        stabilization: {{
          enabled: true,
          iterations: 160,
          updateInterval: 4
        }}
      }},
      interaction: {{
        hover: true,
        tooltipDelay: 120,
        zoomView: true,
        dragView: true,
        dragNodes: true
      }}
    }};

    const network = new vis.Network(container, data, options);

    // Realtime Loading Progress Bar & Percentage
    const progressFill = document.getElementById('progressFill');
    const progressPercent = document.getElementById('progressPercent');
    const loadingStatus = document.getElementById('loadingStatus');
    const loadingScreen = document.getElementById('loadingScreen');

    const statusSteps = [
      {{ max: 25, text: "🛵 Initializing 360 travel locations..." }},
      {{ max: 55, text: "🗺️ Mapping city hubs and inter-city routes..." }},
      {{ max: 80, text: "⚡ Simulating spring physics and gravity forces..." }},
      {{ max: 99, text: "🎨 Styling cartoon nodes and drop shadows..." }},
      {{ max: 100, text: "🚀 Ready! Launching Travel Explorer..." }}
    ];

    let isDismissed = false;

    function renderProgress(p) {{
      if (isDismissed) return;
      const val = Math.min(Math.max(p, 0), 100);
      progressFill.style.width = val + '%';
      progressPercent.textContent = val + '%';

      const step = statusSteps.find(s => val <= s.max) || statusSteps[statusSteps.length - 1];
      loadingStatus.textContent = step.text;
    }}

    network.on('stabilizationProgress', function (params) {{
      const p = Math.round((params.iterations / params.total) * 100);
      renderProgress(p);
    }});

    function dismissLoading() {{
      if (isDismissed) return;
      isDismissed = true;
      renderProgress(100);
      setTimeout(() => {{
        loadingScreen.style.opacity = '0';
        setTimeout(() => {{
          loadingScreen.style.display = 'none';
        }}, 350);
      }}, 300);
    }}

    network.once('stabilizationIterationsDone', function () {{
      dismissLoading();
    }});

    // Safety fallback so screen never hangs
    setTimeout(() => {{
      dismissLoading();
    }}, 3500);

    // Map for fast node lookup
    const nodeMap = new Map();
    rawNodes.forEach(n => nodeMap.set(n.id, n));

    // Drawer Logic
    const drawer = document.getElementById('drawerCard');
    const drawerClose = document.getElementById('drawerClose');
    const drawerTitle = document.getElementById('drawerTitle');
    const drawerBadge = document.getElementById('drawerBadge');
    const drawerLocation = document.getElementById('drawerLocation');
    const drawerDesc = document.getElementById('drawerDesc');
    const drawerTags = document.getElementById('drawerTags');
    const neighborsCount = document.getElementById('neighborsCount');
    const neighborsList = document.getElementById('neighborsList');
    const drawerChatBtn = document.getElementById('drawerChatBtn');

    function openDrawer(nodeId) {{
      const n = nodeMap.get(nodeId);
      if (!n) return;

      drawerTitle.textContent = n.name;
      drawerBadge.textContent = n.type;
      drawerBadge.style.background = n.color.background;
      drawerLocation.textContent = n.city ? ('📍 ' + n.city + (n.region ? ' (' + n.region + ')' : '')) : '📍 Vietnam';
      drawerDesc.textContent = n.description || 'A fascinating Vietnam travel destination.';

      // Tags
      drawerTags.innerHTML = '';
      (n.tags || []).forEach(t => {{
        const span = document.createElement('span');
        span.className = 'drawer-tag';
        span.textContent = '#' + t;
        drawerTags.appendChild(span);
      }});

      // Neighbors
      const connectedNodeIds = network.getConnectedNodes(nodeId);
      neighborsCount.textContent = connectedNodeIds.length;
      neighborsList.innerHTML = '';

      connectedNodeIds.slice(0, 12).forEach(cId => {{
        const neighbor = nodeMap.get(cId);
        if (neighbor) {{
          const pill = document.createElement('span');
          pill.className = 'neighbor-pill';
          pill.innerHTML = `<span>${{neighbor.label.split(' ')[0]}}</span> ${{neighbor.name}}`;
          pill.onclick = () => focusOnNode(cId);
          neighborsList.appendChild(pill);
        }}
      }});

      // Chatbot Link: Send prompt to the existing chat tab and switch to it without closing this graph tab
      drawerChatBtn.onclick = function(e) {{
        if (e) e.preventDefault();
        const chatUrl = '/?q=' + encodeURIComponent('Tell me about ' + n.name + ' in ' + (n.city || 'Vietnam') + ' and top recommendations');

        if (window.opener && !window.opener.closed) {{
          try {{
            window.opener.location.href = chatUrl;
            window.opener.focus();
            return false;
          }} catch (err) {{}}
        }}

        try {{
          const chatWin = window.open(chatUrl, 'vietnam_chat_main');
          if (chatWin) {{
            chatWin.focus();
            return false;
          }}
        }} catch (err) {{}}

        window.open(chatUrl, 'vietnam_chat_main');
        return false;
      }};

      drawer.style.display = 'block';
    }}

    // Switch back to existing chat tab without closing or reloading this graph tab
    function returnToChatbot(event) {{
      if (event) event.preventDefault();

      // 1. If opener tab exists and is open, bring it to front
      if (window.opener && !window.opener.closed) {{
        try {{
          window.opener.focus();
          return false;
        }} catch (err) {{
          console.warn("window.opener focus failed:", err);
        }}
      }}

      // 2. Try focusing the named main chat tab
      try {{
        const chatWin = window.open('', 'vietnam_chat_main');
        if (chatWin) {{
          chatWin.focus();
          return false;
        }}
      }} catch (err) {{
        console.warn("Named window focus failed:", err);
      }}

      // 3. Fallback: open chat in named tab without navigating or closing this tab
      window.open('/', 'vietnam_chat_main');
      return false;
    }}

    drawerClose.onclick = () => {{
      drawer.style.display = 'none';
    }};

    function focusOnNode(nodeId) {{
      network.selectNodes([nodeId]);
      network.focus(nodeId, {{
        scale: 1.35,
        animation: {{
          duration: 900,
          easingFunction: 'easeInOutQuad'
        }}
      }});
      openDrawer(nodeId);
    }}

    // Canvas click event
    network.on('click', function(params) {{
      if (params.nodes.length > 0) {{
        openDrawer(params.nodes[0]);
      }}
    }});

    // Search Autocomplete
    const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');

    searchInput.addEventListener('input', function() {{
      const term = this.value.trim().toLowerCase();
      if (!term) {{
        searchResults.style.display = 'none';
        return;
      }}

      const matches = rawNodes.filter(n => 
        n.name.toLowerCase().includes(term) || 
        n.city.toLowerCase().includes(term) ||
        (n.tags && n.tags.some(t => t.toLowerCase().includes(term)))
      ).slice(0, 8);

      if (matches.length === 0) {{
        searchResults.innerHTML = '<div style="padding:10px; font-size:0.9rem; color:#666;">No places found</div>';
        searchResults.style.display = 'block';
        return;
      }}

      searchResults.innerHTML = '';
      matches.forEach(m => {{
        const div = document.createElement('div');
        div.className = 'search-item';
        div.innerHTML = `
          <span>${{m.label.split(' ')[0]}} <strong>${{m.name}}</strong></span>
          <span style="font-size:0.75rem; background:#eee; padding:2px 6px; border-radius:6px;">${{m.type}}</span>
        `;
        div.onclick = () => {{
          searchInput.value = m.name;
          searchResults.style.display = 'none';
          focusOnNode(m.id);
        }};
        searchResults.appendChild(div);
      }});

      searchResults.style.display = 'block';
    }});

    document.addEventListener('click', function(e) {{
      if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {{
        searchResults.style.display = 'none';
      }}
    }});

    // City Dropdown Jump
    citySelect.addEventListener('change', function() {{
      const cityId = this.value;
      if (cityId) {{
        focusOnNode(cityId);
      }}
    }});

    // Controls
    document.getElementById('btnFit').onclick = () => {{
      network.fit({{ animation: {{ duration: 800, easingFunction: 'easeInOutQuad' }} }});
    }};

    let physicsActive = true;
    const btnPhysics = document.getElementById('btnPhysics');
    const physicsIcon = document.getElementById('physicsIcon');
    btnPhysics.onclick = () => {{
      physicsActive = !physicsActive;
      network.setOptions({{ physics: {{ enabled: physicsActive }} }});
      physicsIcon.textContent = physicsActive ? '⏸️ Freeze' : '▶️ Float';
    }};

    // Jelly Wobble
    document.getElementById('btnJelly').onclick = () => {{
      if (!physicsActive) {{
        physicsActive = true;
        network.setOptions({{ physics: {{ enabled: true }} }});
        physicsIcon.textContent = '⏸️ Freeze';
      }}
      const ids = nodesDataSet.getIds();
      ids.forEach(id => {{
        const pos = network.getPositions([id])[id];
        if (pos) {{
          network.moveNode(id, pos.x + (Math.random() - 0.5) * 45, pos.y + (Math.random() - 0.5) * 45);
        }}
      }});
    }};

    // Category Filter Pills
    const filterPills = document.querySelectorAll('.filter-pill');
    filterPills.forEach(pill => {{
      pill.addEventListener('click', function() {{
        filterPills.forEach(p => p.classList.remove('active'));
        this.classList.add('active');

        const cat = this.getAttribute('data-category');
        if (cat === 'all') {{
          nodesDataSet.forEach(n => {{
            const base = nodeMap.get(n.id);
            nodesDataSet.update({{
              id: n.id,
              hidden: false,
              color: base.color,
              opacity: 1.0
            }});
          }});
          edgesDataSet.forEach(e => edgesDataSet.update({{ id: e.id, hidden: false }}));
        }} else {{
          nodesDataSet.forEach(n => {{
            const base = nodeMap.get(n.id);
            if (base.category === cat) {{
              nodesDataSet.update({{
                id: n.id,
                hidden: false,
                opacity: 1.0
              }});
            }} else {{
              nodesDataSet.update({{
                id: n.id,
                hidden: false,
                opacity: 0.15
              }});
            }}
          }});
        }}
      }});
    }});
  </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"🎉 Generated cartoon knowledge graph visualization: {output_path}")


def main():
    nodes_raw, rels_raw = fetch_graph()
    generate_html(nodes_raw, rels_raw, "neo4j_viz.html")


if __name__ == "__main__":
    main()
