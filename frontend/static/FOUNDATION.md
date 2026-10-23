# Fondation front ZakhrafaAI : contrat des pages (landing / studio / dashboard)
Statique, sans build. URL : `/assets/...` = `frontend/static/...`.
**Ne pas modifier** `tokens.css`, `base.css`, `boot.js`, `i18n.js`, `shell.js`, `http.js`, `ui.js`, `icons.js` ni `i18n/*/common.json`
sans accord : CSS propre à la page dans `css/<page>.css`, JS dans `js/<page>.js` (module ES).

## Squelette obligatoire (ordre exact)
```html
<!doctype html><html lang="fr" dir="ltr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title data-i18n="meta.studio.title">Atelier — ZakhrafaAI</title>
<meta name="description" content="…" data-i18n-attr="content:meta.studio.description">
<script src="/assets/js/boot.js"></script>  <!-- classique, synchrone, AVANT les CSS : lang/dir + .js -->
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Readex+Pro:wght@300..700&family=Inter:wght@400;500;600&family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/assets/css/tokens.css"><link rel="stylesheet" href="/assets/css/base.css">
<link rel="stylesheet" href="/assets/css/studio.css">
</head><body data-page="studio">            <!-- landing | studio | dashboard -->
<header id="site-header"></header>
<main id="main" tabindex="-1"> … texte FR écrit en dur + data-i18n … </main>
<footer id="site-footer"></footer>
<script type="module" src="/assets/js/studio.js"></script></body></html>
```
`js/<page>.js` : `await initI18n("studio"); initShell(); /* puis rendu de la page */ initReveal();`
Landing : `initShell({ sectionLinks: [{ href: "#how", key: "nav.how" }, …] })`. Le CTA d'en-tête est masqué d'office sur studio.
`main` a déjà `padding-top: var(--nav-h)` (en-tête fixe 64px réservé en CSS) ; un hero sous l'en-tête prend `.under-nav`.

## i18n (`js/i18n.js`)
- Fichiers : `i18n/{fr,ar,en}/common.json` (partagé) + `{landing,studio,dashboard}.json` (chaque agent n'édite QUE le sien, dans les 3 langues, mêmes clés).
- common : `meta.lang/dir`, `brand.*`, `a11y.*`, `nav.home|studio|dashboard|cta`, `lang.*`, `footer.*`, `badge.*`, `notice.*`, `error.*`, `common.*`, `palette.*`, `category.<id>.name`, `mode.{fast,ai}.{name,tagline}`.
  landing : `meta.index.*`, `nav.how…about`, `hero.* how.* crafts.* complexity.* category.<id>.{desc,image_alt} modes.* mode.*.{speed,cost,…} gallery.* artisan.* about.* faq.*`. studio : `meta.studio.*`, `studio.*`. dashboard : `meta.dashboard.*`, `dashboard.*`.
- Nouvelle clé : préfixe de la page (`studio.xxx`), clés plates à points, ajoutée en fr+ar+en. Besoin d'une clé commune : la signaler, ne pas l'ajouter.
- HTML : `data-i18n="k"` (textContent, écrase les enfants : mettre icônes et texte dans des éléments frères), `data-i18n-html="k"` (nos JSON seulement),
  `data-i18n-attr="placeholder:k;aria-label:k;title:k;alt:k"`, `data-i18n-params='{"n":3}'` (interpolation `{n}`).
- JS : `t(key, params)` (repli fr puis clé) · `has(key)` · `apply(rootEl)` après injection de HTML à attributs · `getLang() isRTL() getLocale()`
  · `setLang(l)` (sans rechargement, `?lang=`, localStorage `zk.lang`) · `onLangChange(cb)` / événement `document` `i18n:change` {lang,dir,locale} :
  **tout texte rendu en JS doit être re-rendu dans ce callback**. Langue : `?lang=` → localStorage → navigator.languages → fr.
- Formats : `formatNumber`, `formatDate`, `formatTime`, `formatRelative` (« il y a 3 min »). Locale ar = `ar-MA-u-nu-latn` (Maroc, chiffres 0-9
  comme le contenu ; fr-FR, en-GB). Ne jamais formater une seed avec formatNumber. `ltr(v)` renvoie `<bdi dir="ltr" class="ltr">` pour seed / ID / hex / « 256×256 ».

## Composants (`css/base.css`)
- Mise en page : `.container` (`--narrow`) · `.section` (`--tight`, `--band`) · `.section-head` (+`--start`) · `.grid .grid--2|3|4` (1→2→3/4 col) · `.stack` / `.cluster` (`style="--gap:…"`) · `.flow`.
- Typo : `.h1…h4` · `.lead` · `.eyebrow` (+`--lines` hairlines, `--chip` pastille verre) · `.text-grad` · `.muted` `.subtle` `.mono` · `.text-sm|xs`.
- Treillis : `<section class="lattice-host"><div class="lattice" aria-hidden="true"></div>…` ; variantes `.lattice--subtle` (bandes), `--faint` (scène résultat 8 %), `--nofade`.
- Surfaces : `.glass` (`--strong`) · `.panel` · `.card` (`--glass`, `--interactive` + `<a class="stretched">`), `.card__media|title|text|footer` · `.meter[data-level=1-3]`.
- Boutons `.btn` + `--primary` (dégradé safran) `--secondary` `--ghost` `--quiet` `--ai` (IA/payant, sombre+Majorelle) `--ai-solid` (blanc AA) `--danger` ;
  tailles `--sm --lg --block --icon` ; chargement `aria-busy="true"` (spinner auto) ; `disabled`.
- Choix : `.segmented[role=radiogroup] > .segmented__option[role=radio][aria-checked][data-value]` (indicateur glissant) · `.option-grid > .option-card[role=radio]`
  (`--ai` pour Rendu IA ; `.option-card__title|meta`) — les deux pilotés par `initRadioGroup(el, {onChange})` (`ui.js`) : flèches (RTL inversé), Home/End, `change` {value}.
- Formulaires : `.field > .field__label + .input|.textarea|.select + .field__hint|.field__error` ; `aria-invalid="true"` ; `.input--ltr` (seed) ; `.check`.
- `<details class="disclosure">` (+`--boxed`) `<summary>…</summary><div class="disclosure__body">` (FAQ, réglages avancés).
- Badges : `.badge` + `--accent --ai --success --info --danger` · `.dot.dot--zellige|tapis|broderie` · `.chip[aria-pressed]` (filtres).
- Notice : `.notice.notice--info|success|warning|danger|ai` + `role="status"` (ou `alert`) `> icon + .notice__body > .notice__title + p`. Texte : `t("notice."+code)`, inconnu → `notice.service_error`.
- Chargement : `.skeleton` + `--text --title --block --circle` · `.spinner`.
- Utilitaires : `.sr-only .ltr .icon-dir .text-start|center|end .truncate .nowrap .divider .hide-sm .only-sm .hide-mobile .only-mobile`.
- Icônes : `icon(name, {size})` (`icons.js`, chaîne SVG, aria-hidden) : globe menu close chevron-down chevron-end arrow-end arrow-up check star diamond flower bolt sparkle download refresh copy info alert image chart.

## RTL
Propriétés logiques uniquement (`margin-inline-*`, `inset-inline-*`, `padding-block`, `text-align:start`), jamais left/right. `translateX` → multiplier par `var(--dir)` (1 / -1).
Flèches et chevrons : `.icon-dir` (miroir auto) ; ne pas miroiter logo, treillis, images générées, téléchargement. Arabe : aucun letter-spacing (forcé), pas de majuscules,
interlignage haut (jetons). Tester les chaînes FR (les plus longues) et AR (les plus hautes) à 390px : aucun débordement horizontal.

## Mouvement
Uniquement transform/opacity. Révélation : classe `.reveal` (+`style="--i:n"` pour décaler) puis `initReveal()` (contenu visible sans JS ou en mouvement réduit). Entrée du hero : `.enter` + `--i`.
`prefers-reduced-motion` : durées à 0, treillis figé (déjà géré) ; `scrollToEl(el)` (ui.js) respecte ce réglage. Treillis figé sous 481px.

## HTTP (`js/http.js`, remplace `api.js` qui sera retiré)
`const r = await postJSON("/api/generate", body, { timeout: 90000, signal })` / `getJSON("/api/meta")` → jamais d'exception.
Succès `{ok:true, data, status}` ; échec `{ok:false, code, status, data, params}`, code ∈ `network` (coupure, délai, corps tronqué) · `aborted` (signal appelant, ne rien afficher)
· `validation` (422 sans code) · code métier `body.code|detail.code` (→ `error.validation.<code>`) · `http`. `errorMessage(r)` donne le texte traduit. IDs API inchangés : `gan`/`diffusion`.
