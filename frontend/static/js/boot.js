/* ZakhrafaAI — amorçage synchrone (script classique, PAS un module).
   À charger dans <head>, avant les feuilles de style, pour fixer <html lang dir>
   avant le premier rendu (pas de « flash » LTR/français sur une page arabe).
   La résolution de langue DOIT rester identique à resolveLang() de i18n.js :
   ?lang= -> localStorage -> navigator.languages -> fr. */
(function () {
  var SUPPORTED = ["fr", "ar", "en"];
  var KEY = "zk.lang";
  var root = document.documentElement;
  var lang = null;

  function pick(v) {
    if (!v) return null;
    v = String(v).toLowerCase().slice(0, 2);
    return SUPPORTED.indexOf(v) >= 0 ? v : null;
  }

  try { lang = pick(new URLSearchParams(location.search).get("lang")); } catch (e) {}
  if (!lang) { try { lang = pick(localStorage.getItem(KEY)); } catch (e) {} }
  if (!lang) {
    var langs = navigator.languages || [navigator.language];
    for (var i = 0; i < langs.length && !lang; i++) lang = pick(langs[i]);
  }
  lang = lang || "fr";

  root.lang = lang;
  root.dir = lang === "ar" ? "rtl" : "ltr";
  root.classList.add("js");
  // Le HTML est écrit en français : pour ar/en on masque le corps jusqu'à
  // l'application des traductions (i18n.js retire la classe ; secours CSS à 1,5 s).
  if (lang !== "fr") root.classList.add("i18n-pending");
})();
