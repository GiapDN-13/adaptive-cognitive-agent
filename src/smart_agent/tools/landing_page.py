"""Landing page generator — template-based approach.

Agent provides structured JSON content → this tool renders into complete HTML.
"""

import json


def generate_landing_page(config_json: str) -> str:
    """Generate a complete HTML landing page from structured config."""
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON — {e}"

    company = config.get("company_name", "[TÊN CÔNG TY]")
    tagline = config.get("tagline", "[TAGLINE]")
    description = config.get("description", "[MÔ TẢ CÔNG TY]")
    primary_color = config.get("primary_color", "#0E7C6B")
    accent_color = config.get("accent_color", "#2563EB")
    services = config.get("services", [])
    features = config.get("features", [])
    cta_text = config.get("cta_text", "Liên hệ tư vấn")
    contact = config.get("contact", {})
    nav_links = config.get("nav_links", ["Giải pháp", "Về chúng tôi", "Liên hệ"])
    hero_subtitle = config.get("hero_subtitle", description)
    stats = config.get("stats", [])
    testimonials = config.get("testimonials", [])
    footer_text = config.get("footer_text", f"© 2024 {company}. All rights reserved.")

    # Build services HTML
    services_html = ""
    for svc in services:
        name = svc.get("name", "[Dịch vụ]")
        desc = svc.get("description", "[Mô tả]")
        icon = svc.get("icon", "⚡")
        services_html += f"""
      <div class="card">
        <div class="card-icon">{icon}</div>
        <h3>{name}</h3>
        <p>{desc}</p>
      </div>"""

    # Build features HTML
    features_html = ""
    for feat in features:
        features_html += f"""<li class="feature-item">✓ {feat}</li>"""

    # Build stats HTML
    stats_html = ""
    for stat in stats:
        value = stat.get("value", "0")
        label = stat.get("label", "")
        stats_html += f"""
      <div class="stat">
        <div class="stat-value">{value}</div>
        <div class="stat-label">{label}</div>
      </div>"""

    # Build testimonials HTML
    testimonials_html = ""
    for t in testimonials:
        quote = t.get("quote", "[Quote]")
        author = t.get("author", "[Tên]")
        role = t.get("role", "[Chức vụ]")
        testimonials_html += f"""
      <div class="testimonial">
        <p class="quote">"{quote}"</p>
        <div class="author">— <strong>{author}</strong>, {role}</div>
      </div>"""

    # Build nav HTML
    nav_html = "".join(f'<a href="#" class="nav-link">{link}</a>' for link in nav_links)

    # Contact section
    phone = contact.get("phone", "[SĐT]")
    email = contact.get("email", "[EMAIL]")
    address = contact.get("address", "[ĐỊA CHỈ]")

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{company} — {tagline}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    :root {{
      --primary: {primary_color};
      --accent: {accent_color};
      --bg: #0a0a0a;
      --surface: #141414;
      --text: #f0f0f0;
      --muted: #888;
    }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 0 24px; }}

    /* NAV */
    nav {{ display: flex; align-items: center; justify-content: space-between; padding: 20px 40px; border-bottom: 1px solid rgba(255,255,255,0.06); }}
    .logo {{ font-size: 1.5rem; font-weight: 800; color: var(--primary); }}
    .nav-links {{ display: flex; gap: 32px; }}
    .nav-link {{ color: var(--muted); text-decoration: none; transition: color .2s; }}
    .nav-link:hover {{ color: var(--text); }}

    /* HERO */
    .hero {{ padding: 120px 40px; text-align: center; }}
    .hero h1 {{ font-size: 3.5rem; font-weight: 800; margin-bottom: 20px; background: linear-gradient(135deg, var(--primary), var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .hero p {{ font-size: 1.25rem; color: var(--muted); max-width: 700px; margin: 0 auto 40px; }}
    .btn {{ display: inline-block; padding: 14px 32px; background: var(--primary); color: #fff; border-radius: 8px; text-decoration: none; font-weight: 600; transition: transform .2s, box-shadow .2s; }}
    .btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(14,124,107,.3); }}

    /* STATS */
    .stats {{ display: flex; justify-content: center; gap: 60px; padding: 60px 40px; }}
    .stat {{ text-align: center; }}
    .stat-value {{ font-size: 2.5rem; font-weight: 800; color: var(--primary); }}
    .stat-label {{ color: var(--muted); margin-top: 4px; }}

    /* SERVICES */
    .section {{ padding: 80px 40px; }}
    .section-title {{ font-size: 2rem; font-weight: 700; text-align: center; margin-bottom: 48px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; max-width: 1200px; margin: 0 auto; }}
    .card {{ background: var(--surface); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 32px; transition: transform .2s, border-color .2s; }}
    .card:hover {{ transform: translateY(-4px); border-color: var(--primary); }}
    .card-icon {{ font-size: 2rem; margin-bottom: 16px; }}
    .card h3 {{ margin-bottom: 12px; font-size: 1.2rem; }}
    .card p {{ color: var(--muted); font-size: 0.95rem; }}

    /* FEATURES */
    .features {{ list-style: none; max-width: 600px; margin: 0 auto; }}
    .feature-item {{ padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 1.05rem; }}

    /* TESTIMONIALS */
    .testimonials {{ max-width: 800px; margin: 0 auto; }}
    .testimonial {{ background: var(--surface); border-radius: 12px; padding: 32px; margin-bottom: 24px; border-left: 4px solid var(--primary); }}
    .quote {{ font-size: 1.1rem; font-style: italic; margin-bottom: 16px; }}
    .author {{ color: var(--muted); }}

    /* CONTACT */
    .contact-info {{ text-align: center; padding: 40px; }}
    .contact-info p {{ margin: 8px 0; color: var(--muted); }}

    /* FOOTER */
    footer {{ text-align: center; padding: 40px; border-top: 1px solid rgba(255,255,255,0.06); color: var(--muted); font-size: 0.9rem; }}

    @media (max-width: 768px) {{
      .hero h1 {{ font-size: 2.2rem; }}
      .stats {{ flex-direction: column; gap: 24px; }}
      nav {{ flex-direction: column; gap: 16px; }}
    }}
  </style>
</head>
<body>
  <nav>
    <div class="logo">{company}</div>
    <div class="nav-links">{nav_html}</div>
    <a href="#contact" class="btn">{cta_text}</a>
  </nav>

  <section class="hero">
    <h1>{tagline}</h1>
    <p>{hero_subtitle}</p>
    <a href="#contact" class="btn">{cta_text}</a>
  </section>

  {"<section class='stats'>" + stats_html + "</section>" if stats else ""}

  <section class="section" id="services">
    <h2 class="section-title">Dịch vụ & Giải pháp</h2>
    <div class="cards">{services_html}
    </div>
  </section>

  {"<section class='section'><h2 class='section-title'>Tại sao chọn " + company + "?</h2><ul class='features'>" + features_html + "</ul></section>" if features else ""}

  {"<section class='section'><h2 class='section-title'>Khách hàng nói gì</h2><div class='testimonials'>" + testimonials_html + "</div></section>" if testimonials else ""}

  <section class="section" id="contact">
    <h2 class="section-title">Liên hệ</h2>
    <div class="contact-info">
      <p>📞 {phone}</p>
      <p>✉️ {email}</p>
      <p>📍 {address}</p>
      <a href="mailto:{email}" class="btn" style="margin-top:24px;">{cta_text}</a>
    </div>
  </section>

  <footer>{footer_text}</footer>
</body>
</html>"""

    return html
