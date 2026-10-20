# Tandoor Recipes for Home Assistant

Bring your self-hosted [Tandoor Recipes](https://tandoor.dev) meal plan into Home Assistant, with a **What's for dinner?** card included.

- 🍽️ **Dinner tonight**: the recipe on today's meal plan. When nothing is planned, it suggests a recipe from your library.
- 🎲 **Suggest another**: a button (and a tap in the card) that picks a different idea.
- 📅 **Meal plan calendar**: every planned meal as a calendar entity, so it works with the calendar card, automations and voice assistants.
- 🖼️ **Recipe photo through HA**: the photo is served by Home Assistant, so it loads away from home too.
- 🃏 **Tandoor Dinner card**: bundled and registered automatically. There's nothing extra to install.

Everything stays on your network. HA talks to your Tandoor server directly with a read-only API token.

## Requirements

- Home Assistant 2025.2 or newer
- Tandoor Recipes 2.x, reachable from Home Assistant

## Installation

### HACS (recommended)

1. Open **HACS**, then use the three-dot menu → **Custom repositories**.
2. Add `https://github.com/Natefishcodes/ha-tandoor` with the category **Integration**.
3. Search for **Tandoor Recipes**, download it, and restart Home Assistant.

### Manual

Copy `custom_components/tandoor` into your Home Assistant `config/custom_components/` folder, then restart.

## Setup

1. In Tandoor, go to **Settings → API** and create a token. Read access is enough.
2. In Home Assistant, go to **Settings → Devices & services → Add integration → Tandoor Recipes**.
3. Enter your Tandoor address (for example `http://192.168.1.20:8080`) and paste the token.

**Options** (on the integration's **Configure** button):

| Option | Default | What it does |
| --- | --- | --- |
| Meal types that count as dinner | *Dinner / Supper* | Pick your own if your meal types are named differently, or to make "dinner" your lunch |
| Update interval | 15 min | How often the meal plan is checked |

## Entities

| Entity | What it shows |
| --- | --- |
| `sensor.tandoor_recipes_dinner_tonight` | Recipe name. Attributes: `source` (`meal_plan` / `suggestion` / `none`), `recipe_url`, `image_url`, `description`, `working_time`, `waiting_time`, `total_time`, `servings`, `rating`, `meal_type`, `note` |
| `sensor.tandoor_recipes_meals_today` | Number of meals planned today, with a `meals` list |
| `calendar.tandoor_recipes_meal_plan` | The meal plan. Meals with a time on their meal type (e.g. Dinner 18:00) are timed; others are all-day |
| `image.tandoor_recipes_dinner_photo` | Photo of tonight's recipe |
| `button.tandoor_recipes_suggest_another` | Picks a new random suggestion |

The suggestion changes automatically once a day.

## The card

Add a card and search for **Tandoor Dinner**, or use YAML:

```yaml
type: custom:tandoor-dinner-card
```

The card finds its entities automatically. Every option is in the visual editor:

| Option | Default | |
| --- | --- | --- |
| `title` | none | Card header |
| `accent_color` | theme primary | An HA color name (`red`, `amber`, …) or any CSS color |
| `image_height` | `200` | Photo height in px; `0` hides it |
| `show_stats` | `true` | Prep, cook, total time, servings, rating |
| `show_description` | `true` | First lines of the recipe description |
| `entity`, `image_entity`, `suggest_entity` | auto | Only needed with several Tandoor instances |

**Automation idea:** announce dinner at 5 PM.

```yaml
triggers:
  - trigger: time
    at: "17:00:00"
actions:
  - action: notify.notify
    data:
      message: "Tonight: {{ states('sensor.tandoor_recipes_dinner_tonight') }}"
```

## Troubleshooting

- **"Tandoor rejected the API token"**: create a new token. HA will also ask for one by itself if the token stops working.
- **Photo missing**: the recipe has no image in Tandoor, or HA can't reach Tandoor's `/media/` path.
- **Diagnostics**: on the integration's page, use **⋮ → Download diagnostics**. The token is always redacted.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

`preview/index.html` renders the card with sample data and needs no Home Assistant. Serve the repo with `python3 -m http.server` and open `/preview/`.

## License

MIT
