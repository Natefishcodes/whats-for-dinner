/*
 * Tandoor Dinner Card — ships with the Tandoor Recipes integration.
 *
 *   type: custom:tandoor-dinner-card
 *   # everything below is optional; entities are found automatically
 *   entity: sensor.tandoor_recipes_dinner_tonight
 *   image_entity: image.tandoor_recipes_dinner_photo
 *   suggest_entity: button.tandoor_recipes_suggest_another
 *   title: What's for dinner?
 *   days: 1                    # 1 = tonight, 3 = next three days, 7 = the week
 *   accent_color: red          # HA color name or any CSS color
 *   image_height: 200
 *   show_stats: true
 *   show_description: true
 */

const CARD_VERSION = "0.2.0";
const DAY_OPTIONS = [
  { value: "1", label: "Tonight" },
  { value: "3", label: "Next 3 days" },
  { value: "7", label: "The week" },
];
const PLATFORM = "tandoor";

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const safeUrl = (value) => (/^https?:\/\//i.test(value || "") ? value : "");

function findEntity(hass, domain, translationKey) {
  const entities = hass?.entities || {};
  return Object.keys(entities).find(
    (id) => id.startsWith(`${domain}.`) && entities[id].platform === PLATFORM && entities[id].translation_key === translationKey,
  );
}

function accent(color) {
  if (!color) return "var(--primary-color)";
  return /^[a-z][a-z-]*$/.test(color) && !["transparent", "white", "black"].includes(color)
    ? `var(--${color}-color, ${color})`
    : color;
}

class TandoorDinnerCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        { name: "entity", selector: { entity: { domain: "sensor", integration: PLATFORM } } },
        {
          type: "grid",
          name: "",
          schema: [
            { name: "image_entity", selector: { entity: { domain: "image", integration: PLATFORM } } },
            { name: "suggest_entity", selector: { entity: { domain: "button", integration: PLATFORM } } },
          ],
        },
        {
          type: "grid",
          name: "",
          schema: [
            { name: "days", selector: { select: { mode: "dropdown", options: DAY_OPTIONS } } },
            { name: "title", selector: { text: {} } },
          ],
        },
        {
          type: "grid",
          name: "",
          schema: [
            { name: "accent_color", selector: { ui_color: {} } },
            { name: "image_height", selector: { number: { min: 0, max: 480, step: 10, unit_of_measurement: "px" } } },
          ],
        },
        {
          type: "grid",
          name: "",
          schema: [
            { name: "show_stats", selector: { boolean: {} } },
            { name: "show_description", selector: { boolean: {} } },
          ],
        },
      ],
      computeLabel: (s) =>
        ({
          entity: "Dinner sensor (auto-detected)",
          image_entity: "Photo (auto-detected)",
          suggest_entity: "Suggest button (auto-detected)",
          title: "Title (optional)",
          days: "Show",
          accent_color: "Accent color",
          image_height: "Photo height (0 hides photos)",
          show_stats: "Show times & servings",
          show_description: "Show description",
        })[s.name],
    };
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { image_height: 200, show_stats: true, show_description: true, days: 1, ...config };
    this._signature = undefined;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  get _days() {
    const d = Number(this._config.days);
    return [3, 7].includes(d) ? d : 1;
  }

  getCardSize() {
    return this._days === 1 ? 6 : 2 + this._days;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _ids() {
    const c = this._config;
    const h = this._hass;
    return {
      sensor: c.entity || findEntity(h, "sensor", "dinner_tonight"),
      image: c.image_entity || findEntity(h, "image", "dinner_photo"),
      button: c.suggest_entity || findEntity(h, "button", "suggest_another"),
    };
  }

  _render() {
    if (!this._config || !this._hass || !this.shadowRoot) return;
    const ids = this._ids();
    const st = (id) => (id ? this._hass.states[id] : undefined);
    const sensor = st(ids.sensor);
    const image = st(ids.image);
    const button = st(ids.button);

    // Re-render only when something the card shows has changed.
    const signature = [sensor?.last_updated, image?.attributes?.entity_picture, button?.state, JSON.stringify(this._config), this._busy].join("|");
    if (signature === this._signature) return;
    this._signature = signature;

    if (!sensor) {
      this.shadowRoot.innerHTML = this._shell(
        `<div class="empty"><ha-icon icon="mdi:chef-hat"></ha-icon><div>Tandoor Recipes isn't set up yet.<br><small>Add the integration under Settings → Devices &amp; services.</small></div></div>`,
      );
      return;
    }

    const a = sensor.attributes || {};
    const source = a.source || "none";
    const name = sensor.state && !["unknown", "unavailable"].includes(sensor.state) ? sensor.state : "";
    if (source === "none" || !name) {
      this.shadowRoot.innerHTML = this._shell(
        `<div class="empty"><ha-icon icon="mdi:silverware-variant"></ha-icon><div>Nothing planned, and no recipes to suggest.<br><small>Add a dinner to your Tandoor meal plan.</small></div></div>`,
      );
      return;
    }

    const planned = source === "meal_plan";
    const c = this._config;
    if (this._days > 1 && Array.isArray(a.upcoming) && a.upcoming.length) {
      this._renderDays(a, name, planned, ids, button);
      return;
    }
    const picture = image?.state !== "unavailable" ? image?.attributes?.entity_picture : undefined;
    const imgSrc = picture ? this._hass.hassUrl(picture) : safeUrl(a.image_url);
    const height = Number(c.image_height) || 0;

    const stats = [];
    if (a.working_time) stats.push(["mdi:knife", `${a.working_time} min prep`]);
    if (a.waiting_time) stats.push(["mdi:fire", `${a.waiting_time} min cook`]);
    if (a.working_time && a.waiting_time) stats.push(["mdi:timer-outline", `${a.total_time} min total`]);
    if (a.servings) stats.push(["mdi:account-group", `${Math.round(a.servings * 10) / 10} servings`]);
    if (a.rating) stats.push([null, "★".repeat(Math.max(1, Math.min(5, Math.round(a.rating))))]);

    const tag = planned
      ? `<span class="tag planned"><ha-icon icon="mdi:calendar-check"></ha-icon>${esc(a.meal_type || "Dinner")} tonight</span>`
      : `<span class="tag idea"><ha-icon icon="mdi:lightbulb-on-outline"></ha-icon>Nothing planned · how about…</span>`;

    const hero = height
      ? `<div class="hero" style="height:${height}px">
           ${imgSrc ? `<img src="${esc(imgSrc)}" alt="" loading="lazy">` : `<div class="placeholder"><ha-icon icon="mdi:pot-steam"></ha-icon></div>`}
           <div class="shade"></div>
           <div class="overlay">${tag}<div class="name">${esc(name)}</div></div>
         </div>`
      : `<div class="plain">${tag}<div class="name">${esc(name)}</div></div>`;

    const statsHtml =
      c.show_stats && stats.length
        ? `<div class="stats">${stats.map(([icon, text]) => `<span class="stat">${icon ? `<ha-icon icon="${icon}"></ha-icon>` : ""}${esc(text)}</span>`).join("")}</div>`
        : "";
    const desc = c.show_description && a.description ? `<p class="desc">${esc(a.description)}</p>` : "";
    const note = planned && a.note ? `<p class="note"><ha-icon icon="mdi:note-text-outline"></ha-icon>${esc(a.note)}</p>` : "";

    const url = safeUrl(a.recipe_url);
    const actions = [
      url ? `<a class="btn primary" href="${esc(url)}" target="_blank" rel="noopener"><ha-icon icon="mdi:book-open-variant"></ha-icon>Open recipe</a>` : "",
      !planned && ids.button && button
        ? `<button class="btn" id="suggest" ${this._busy ? "disabled" : ""}><ha-icon icon="mdi:dice-multiple"></ha-icon>${this._busy ? "Picking…" : "Suggest another"}</button>`
        : "",
    ].join("");

    this.shadowRoot.innerHTML = this._shell(
      `${hero}<div class="body">${statsHtml}${note}${desc}${actions ? `<div class="actions">${actions}</div>` : ""}</div>`,
    );
    this.shadowRoot.getElementById("suggest")?.addEventListener("click", () => this._suggest(ids.button));
  }

  // Several days as a list. Tonight's row falls back to the suggestion when nothing is planned.
  _renderDays(a, tonightName, plannedTonight, ids, button) {
    const c = this._config;
    const photos = (Number(c.image_height) || 0) > 0;
    const label = (iso, i) => {
      if (i === 0) return "Tonight";
      if (i === 1) return "Tomorrow";
      const d = new Date(`${iso}T12:00:00`);
      return d.toLocaleDateString(undefined, { weekday: "long" });
    };
    const rows = a.upcoming.slice(0, this._days).map((row, i) => {
      const idea = i === 0 && !row.name && !plannedTonight;
      const name = row.name || (idea ? tonightName : "");
      const img = safeUrl(row.image_url || (idea ? a.image_url : ""));
      const url = safeUrl(row.recipe_url || (idea ? a.recipe_url : ""));
      const time = row.total_time || (idea ? a.total_time : 0);
      const date = new Date(`${row.date}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
      const thumb = photos
        ? `<span class="thumb">${img ? `<img src="${esc(img)}" alt="" loading="lazy">` : `<ha-icon icon="${name ? "mdi:pot-steam" : "mdi:silverware-variant"}"></ha-icon>`}</span>`
        : "";
      const what = name
        ? `<span class="dish">${esc(name)}</span>`
        : `<span class="dish none">Nothing planned</span>`;
      const meta = [idea ? "Idea" : "", time ? `${time} min` : ""].filter(Boolean).join(" · ");
      const inner = `${thumb}<span class="when"><b>${esc(label(row.date, i))}</b><small>${esc(date)}</small></span>
        <span class="what">${what}${meta ? `<small>${esc(meta)}</small>` : ""}</span>
        ${url ? `<ha-icon class="go" icon="mdi:chevron-right"></ha-icon>` : ""}`;
      const cls = `day ${i === 0 ? "today" : ""} ${idea ? "idea" : ""} ${name ? "" : "empty"}`;
      return url
        ? `<a class="${cls}" href="${esc(url)}" target="_blank" rel="noopener">${inner}</a>`
        : `<div class="${cls}">${inner}</div>`;
    }).join("");
    const suggest = !plannedTonight && ids.button && button
      ? `<div class="actions"><button class="btn" id="suggest" ${this._busy ? "disabled" : ""}><ha-icon icon="mdi:dice-multiple"></ha-icon>${this._busy ? "Picking…" : "Another idea for tonight"}</button></div>`
      : "";
    this.shadowRoot.innerHTML = this._shell(`<div class="days n${this._days}">${rows}</div>${suggest ? `<div class="body">${suggest}</div>` : ""}`);
    this.shadowRoot.getElementById("suggest")?.addEventListener("click", () => this._suggest(ids.button));
  }

  async _suggest(buttonId) {
    if (this._busy) return;
    this._busy = true;
    this._render();
    try {
      await this._hass.callService("button", "press", { entity_id: buttonId });
    } finally {
      this._busy = false;
      this._signature = undefined;
      this._render();
    }
  }

  _shell(content) {
    const c = this._config;
    const title = c.title ? `<div class="header">${esc(c.title)}</div>` : "";
    return `<style>${STYLES}</style><ha-card style="--tdc-accent:${accent(c.accent_color)}">${title}${content}</ha-card>`;
  }
}

const STYLES = `
  ha-card { overflow: hidden; }
  .header { padding: 16px 16px 0; font-size: 1.25rem; font-weight: 500; }
  .hero { position: relative; overflow: hidden; background: var(--secondary-background-color); }
  .header + .hero { margin-top: 12px; }
  .hero img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .placeholder { width: 100%; height: 100%; display: grid; place-items: center;
    background: linear-gradient(135deg, color-mix(in srgb, var(--tdc-accent) 35%, transparent), var(--secondary-background-color)); }
  .placeholder ha-icon { --mdc-icon-size: 64px; color: var(--tdc-accent); opacity: .8; }
  .shade { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,.72) 0%, rgba(0,0,0,.15) 55%, transparent 100%); }
  .overlay { position: absolute; left: 0; right: 0; bottom: 0; padding: 14px 16px; color: #fff; }
  .plain { padding: 16px 16px 0; }
  .name { font-size: 1.5rem; font-weight: 600; line-height: 1.2; margin-top: 6px; text-wrap: balance; }
  .tag { display: inline-flex; align-items: center; gap: 4px; font-size: .75rem; font-weight: 600; letter-spacing: .02em;
    padding: 3px 10px 3px 6px; border-radius: 999px; }
  .tag ha-icon { --mdc-icon-size: 16px; }
  .tag.planned { background: var(--tdc-accent); color: var(--text-primary-color, #fff); }
  .tag.idea { background: rgba(255,255,255,.9); color: #222; }
  .plain .tag.idea { background: color-mix(in srgb, var(--tdc-accent) 18%, transparent); color: var(--primary-text-color); }
  .body { padding: 12px 16px 16px; display: flex; flex-direction: column; gap: 10px; }
  .stats { display: flex; flex-wrap: wrap; gap: 6px; }
  .stat { display: inline-flex; align-items: center; gap: 4px; font-size: .85rem; padding: 4px 10px; border-radius: 999px;
    background: var(--secondary-background-color); color: var(--primary-text-color); }
  .stat ha-icon { --mdc-icon-size: 16px; color: var(--tdc-accent); }
  .desc { margin: 0; color: var(--secondary-text-color); line-height: 1.45;
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  .note { margin: 0; display: flex; gap: 6px; align-items: flex-start; font-style: italic; color: var(--primary-text-color); }
  .note ha-icon { --mdc-icon-size: 18px; color: var(--tdc-accent); flex: none; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .btn { flex: 1 1 140px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 40px;
    padding: 0 14px; border-radius: 12px; font: inherit; font-weight: 600; font-size: .9rem; cursor: pointer; text-decoration: none;
    border: 1px solid color-mix(in srgb, var(--tdc-accent) 45%, transparent); background: transparent; color: var(--primary-text-color); }
  .btn ha-icon { --mdc-icon-size: 18px; }
  .btn.primary { background: var(--tdc-accent); border-color: transparent; color: var(--text-primary-color, #fff); }
  .btn:disabled { opacity: .6; cursor: progress; }
  .btn:focus-visible { outline: 2px solid var(--tdc-accent); outline-offset: 2px; }
  .empty { display: flex; gap: 12px; align-items: center; padding: 20px 16px; color: var(--secondary-text-color); }
  .days { display: flex; flex-direction: column; padding: 8px; gap: 2px; }
  .header + .days { padding-top: 10px; }
  .day { display: grid; grid-template-columns: auto 92px 1fr auto; align-items: center; gap: 12px; padding: 8px 10px;
    border-radius: 12px; color: inherit; text-decoration: none; }
  .day:not(:has(.thumb)) { grid-template-columns: 92px 1fr auto; }
  a.day:hover { background: var(--secondary-background-color); }
  .day.today { background: color-mix(in srgb, var(--tdc-accent) 12%, transparent); }
  .thumb { width: 48px; height: 48px; border-radius: 10px; overflow: hidden; display: grid; place-items: center;
    background: var(--secondary-background-color); }
  .n7 .thumb { width: 36px; height: 36px; border-radius: 8px; }
  .thumb img { width: 100%; height: 100%; object-fit: cover; }
  .thumb ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  .when { display: flex; flex-direction: column; line-height: 1.2; }
  .when b { font-weight: 600; font-size: .9rem; }
  .today .when b { color: var(--tdc-accent); }
  .when small, .what small { color: var(--secondary-text-color); font-size: .78rem; }
  .what { display: flex; flex-direction: column; min-width: 0; line-height: 1.25; }
  .dish { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dish.none { color: var(--secondary-text-color); font-weight: 400; font-style: italic; }
  .day.idea .dish::before { content: "💡 "; }
  .go { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  .empty ha-icon { --mdc-icon-size: 36px; color: var(--tdc-accent); flex: none; }
`;

if (!customElements.get("tandoor-dinner-card")) {
  customElements.define("tandoor-dinner-card", TandoorDinnerCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "tandoor-dinner-card",
    name: "Tandoor Dinner",
    description: "Tonight's dinner from your Tandoor meal plan, or a suggestion when nothing is planned.",
    preview: true,
    documentationURL: "https://github.com/Natefishcodes/whats-for-dinner",
  });
  console.info(`%c TANDOOR-DINNER-CARD %c ${CARD_VERSION} `, "background:#e2342b;color:#fff;border-radius:3px 0 0 3px", "background:#333;color:#fff;border-radius:0 3px 3px 0");
}
