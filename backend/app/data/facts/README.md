# Fun-fact packs (companion fallback / orb / Home "Did you know?" card)

Drop a plain-text `*.txt` file in this folder and restart the backend — it is
picked up automatically. **No code change is needed to add a category.**

## Rules

- **The filename is the category.** `gaming_facts.txt` → "Gaming",
  `1000_world_facts.txt` → "World", `love_and_romance_facts.txt` → "Love and
  Romance". The tokens `1000`, `facts`, `fact`, `truly`, `unique` are stripped
  and the rest is title-cased. Two files that resolve to the same category are
  merged.
- **Only `N. <fact>` lines become facts.** A line must start with a number, a
  dot, and a space (`12. Honey never spoils.`). The number is removed; the rest
  is the fact shown to the user.
- **Everything else is ignored automatically** — so a number, heading or title
  can never leak to a user. That includes:
  - title banners like `1000 FACTS ABOUT FOOD` (space after the number, not a
    dot — so it is not a fact line),
  - `====` / `----` rule lines,
  - section dividers like `--- ASIA ---`,
  - `END OF 1000 … FACTS` footers,
  - blank lines.

You can therefore paste a whole 1000-line pack in any of the supported layouts
(plain numbered, or with a banner + section dividers + footer) and it just works.

## Encoding

Save as UTF-8. Files are read as UTF-8 with replacement for stray bytes, so a
mis-encoded character degrades to `�` rather than breaking the pack.

## Where else facts live

The Flutter app bundles a small starter copy in `mobile/assets/facts/` so the
companion still has facts with no network. When the backend is reachable the app
caches these packs locally and prefers them. Facts are **fallback** content: the
companion only speaks a fact when it has nothing user-specific to say.
