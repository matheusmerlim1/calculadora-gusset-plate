/*
 * site.js
 * =======
 * Comportamento da pagina do projeto: tema claro/escuro, menu no celular,
 * navegacao com destaque da secao atual, abas, ampliacao de imagem e a
 * demonstracao ao vivo da secao de Whitmore.
 *
 * O calculo em si mora em js/whitmore.js, que e um porte verificado de
 * src/gusset_calc.py (ver tests/test_whitmore_js.mjs).
 */
(function () {
  "use strict";

  var $  = function (sel, ctx) { return (ctx || document).querySelector(sel); };
  var $$ = function (sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); };

  /* ------------------------------------------------------------------ tema */

  var CHAVE_TEMA = "gusset-tema";

  function lerTema() {
    try { return localStorage.getItem(CHAVE_TEMA); } catch (e) { return null; }
  }
  function gravarTema(v) {
    try { localStorage.setItem(CHAVE_TEMA, v); } catch (e) { /* modo privado */ }
  }

  function temaAtual() {
    var fixo = document.documentElement.getAttribute("data-theme");
    if (fixo) return fixo;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function iniciarTema() {
    var salvo = lerTema();
    if (salvo === "dark" || salvo === "light") {
      document.documentElement.setAttribute("data-theme", salvo);
    }
    var botao = $(".theme-toggle");
    if (!botao) return;
    botao.addEventListener("click", function () {
      var novo = temaAtual() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", novo);
      gravarTema(novo);
      botao.setAttribute("aria-label",
        novo === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro");
      desenharWhitmore();   // o desenho usa as cores do tema
    });
  }

  /* ---------------------------------------------------- cabecalho e menu */

  function iniciarCabecalho() {
    var header = $(".site-header");
    var nav = $(".site-nav");
    var toggle = $(".nav-toggle");

    if (header) {
      var marcar = function () {
        header.classList.toggle("is-stuck", window.scrollY > 4);
      };
      marcar();
      window.addEventListener("scroll", marcar, { passive: true });
    }

    if (toggle && nav) {
      toggle.addEventListener("click", function () {
        var aberto = nav.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", aberto ? "true" : "false");
      });
      nav.addEventListener("click", function (ev) {
        if (ev.target.tagName === "A") {
          nav.classList.remove("is-open");
          toggle.setAttribute("aria-expanded", "false");
        }
      });
    }
  }

  /* ------------------------------------------- destaque da secao atual */

  function iniciarScrollSpy() {
    var links = $$(".site-nav a[href^='#']");
    if (!links.length || !("IntersectionObserver" in window)) return;

    var porId = {};
    var alvos = [];
    links.forEach(function (a) {
      var alvo = document.getElementById(a.getAttribute("href").slice(1));
      if (alvo) { porId[alvo.id] = a; alvos.push(alvo); }
    });

    var visiveis = {};
    var obs = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) { visiveis[e.target.id] = e.isIntersecting; });
      var atual = null;
      alvos.forEach(function (alvo) { if (visiveis[alvo.id] && !atual) atual = alvo.id; });
      links.forEach(function (a) { a.classList.remove("is-active"); });
      if (atual && porId[atual]) porId[atual].classList.add("is-active");
    }, { rootMargin: "-35% 0px -55% 0px", threshold: 0 });

    alvos.forEach(function (alvo) { obs.observe(alvo); });
  }

  /* ------------------------------------------------------- revelar ao rolar */

  function iniciarReveal() {
    var itens = $$(".reveal");
    if (!itens.length) return;
    if (!("IntersectionObserver" in window)) {
      itens.forEach(function (el) { el.classList.add("is-in"); });
      return;
    }
    var obs = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add("is-in");
        obs.unobserve(e.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
    itens.forEach(function (el) { obs.observe(el); });
  }

  /* ------------------------------------------------------------------ abas */

  function iniciarAbas() {
    var lista = $(".tablist");
    if (!lista) return;
    var botoes = $$("button", lista);

    function selecionar(indice, focar) {
      botoes.forEach(function (b, i) {
        var ativo = i === indice;
        b.setAttribute("aria-selected", ativo ? "true" : "false");
        b.setAttribute("tabindex", ativo ? "0" : "-1");
        var painel = document.getElementById(b.getAttribute("aria-controls"));
        if (painel) painel.hidden = !ativo;
        if (ativo && focar) b.focus();
      });
    }

    botoes.forEach(function (b, i) {
      b.addEventListener("click", function () { selecionar(i, false); });
      b.addEventListener("keydown", function (ev) {
        var passo = ev.key === "ArrowRight" ? 1 : ev.key === "ArrowLeft" ? -1 : 0;
        if (passo) {
          ev.preventDefault();
          selecionar((i + passo + botoes.length) % botoes.length, true);
        } else if (ev.key === "Home") {
          ev.preventDefault(); selecionar(0, true);
        } else if (ev.key === "End") {
          ev.preventDefault(); selecionar(botoes.length - 1, true);
        }
      });
    });

    selecionar(0, false);
  }

  /* -------------------------------------------------------------- lightbox */

  function iniciarLightbox() {
    var caixa = $(".lightbox");
    if (!caixa) return;
    var img = $("img", caixa);
    var cap = $(".lightbox-cap", caixa);
    var ultimoFoco = null;

    function abrir(src, alt, legenda) {
      ultimoFoco = document.activeElement;
      img.src = src;
      img.alt = alt || "";
      cap.textContent = legenda || "";
      caixa.classList.add("is-open");
      caixa.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
      $(".lightbox-close", caixa).focus();
    }

    function fechar() {
      caixa.classList.remove("is-open");
      caixa.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
      if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
    }

    document.addEventListener("click", function (ev) {
      var alvo = ev.target.closest ? ev.target.closest(".zoomable img") : null;
      if (!alvo) return;
      var fig = alvo.closest("figure, .window");
      var legenda = "";
      if (fig) {
        var fc = fig.querySelector("figcaption") || fig.querySelector(".window-bar span");
        if (fc) legenda = fc.textContent.trim();
      }
      abrir(alvo.currentSrc || alvo.src, alvo.alt, legenda);
    });

    caixa.addEventListener("click", function (ev) {
      if (ev.target === caixa || ev.target.closest(".lightbox-close")) fechar();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && caixa.classList.contains("is-open")) fechar();
    });
  }

  /* ------------------------------------------------- demonstracao ao vivo */

  var demo = null;

  var PRESETS = {
    exemplo: { L: 13.0, s: 3.0, tp: 0.500, Fy: 50, K: 0.5, Lc: 5.0, Pu: 127 },
    esbelta: { L: 8.0,  s: 0.0, tp: 0.250, Fy: 36, K: 1.2, Lc: 18.0, Pu: 60 },
    robusta: { L: 18.0, s: 4.0, tp: 0.750, Fy: 50, K: 0.65, Lc: 8.0, Pu: 420 }
  };

  var E_ACO = 29000;      // ksi - modulo de elasticidade do aco
  var PHI_Y = 0.90;
  var PHI_C = 0.90;

  function iniciarDemo() {
    var raiz = $("#demo-whitmore");
    if (!raiz || !window.Whitmore) return;

    demo = {
      raiz: raiz,
      campos: {},
      svg: $("#viz-whitmore", raiz),
      saidas: {}
    };

    ["L", "s", "tp", "Fy", "K", "Lc", "Pu"].forEach(function (nome) {
      var input = $("#in-" + nome, raiz);
      if (input) {
        demo.campos[nome] = input;
        input.addEventListener("input", atualizarDemo);
      }
    });

    ["Lw", "Aw", "KLr", "Fcr", "phiPny", "phiPnb"].forEach(function (nome) {
      demo.saidas[nome] = $("#out-" + nome, raiz);
    });

    var preset = $("#in-preset", raiz);
    if (preset) {
      preset.addEventListener("change", function () {
        var p = PRESETS[preset.value];
        if (!p) return;
        Object.keys(p).forEach(function (k) {
          if (demo.campos[k]) demo.campos[k].value = p[k];
        });
        atualizarDemo();
      });
    }

    window.addEventListener("resize", desenharWhitmore);
    atualizarDemo();
  }

  function lerDemo() {
    var v = {};
    Object.keys(demo.campos).forEach(function (k) {
      v[k] = parseFloat(demo.campos[k].value);
    });
    v.E = E_ACO;
    v.phi_y = PHI_Y;
    v.phi_c = PHI_C;
    return v;
  }

  function fmt(x, casas) {
    if (!isFinite(x)) return "--";
    return x.toFixed(casas === undefined ? 2 : casas);
  }

  function atualizarDemo() {
    if (!demo) return;
    var ent = lerDemo();
    var r = window.Whitmore.check(ent);

    // valores mostrados junto de cada controle
    Object.keys(demo.campos).forEach(function (k) {
      var saida = $("#val-" + k, demo.raiz);
      if (!saida) return;
      var casas = (k === "tp" || k === "K") ? (k === "tp" ? 3 : 2) : 1;
      saida.textContent = fmt(ent[k], casas) + (UNIDADE[k] || "");
    });

    def(demo.saidas.Lw, fmt(r.Lw, 2), "in");
    def(demo.saidas.Aw, fmt(r.Aw, 2), "in&sup2;");
    def(demo.saidas.KLr, fmt(r.KL_r, 1), "");
    def(demo.saidas.Fcr, fmt(r.Fcr, 1), "ksi");
    def(demo.saidas.phiPny, fmt(r.phiPn_yield, 1), "kips");
    def(demo.saidas.phiPnb, fmt(r.phiPn_buckling, 1), "kips");

    barra("dcr-y", r.DCR_yield);
    barra("dcr-b", r.DCR_buckling);

    desenharWhitmore(r, ent);
  }

  var UNIDADE = { L: " in", s: " in", tp: " in", Fy: " ksi", K: "", Lc: " in", Pu: " kips" };

  function def(el, valor, unidade) {
    if (!el) return;
    el.innerHTML = valor + (unidade ? ' <small>' + unidade + "</small>" : "");
  }

  function barra(id, dcr) {
    var linha = document.getElementById(id);
    if (!linha) return;
    var largura = Math.max(0, Math.min(1, isFinite(dcr) ? dcr : 1)) * 100;
    var preenchimento = $("i", linha);
    var valor = $(".dcr-val", linha);
    if (preenchimento) preenchimento.style.width = largura.toFixed(1) + "%";
    if (valor) valor.textContent = isFinite(dcr) ? dcr.toFixed(2) : "--";
    linha.classList.toggle("is-over", isFinite(dcr) && dcr > 1);
  }

  /* Desenho do espalhamento de Whitmore: a linha de conectores de
     comprimento L, as duas retas a 30 graus e a largura resultante Lw. */
  function desenharWhitmore(r, ent) {
    if (!demo || !demo.svg) return;
    if (!r) {
      ent = lerDemo();
      r = window.Whitmore.check(ent);
    }

    var estilo = getComputedStyle(document.documentElement);
    var cor = function (nome, alt) {
      var c = estilo.getPropertyValue(nome).trim();
      return c || alt;
    };
    var corLinha  = cor("--navy", "#1c3d6e");
    var corAcento = cor("--accent", "#8e2c2c");
    var corVerde  = cor("--green", "#1c6b45");
    var corTexto  = cor("--muted", "#64707f");

    var W = 520, H = 300;
    var L = Math.max(ent.L, 0.001);
    var Lw = r.Lw;

    // escala: cabem L na horizontal e Lw na vertical, com folga
    var margemX = 78, margemY = 42;
    var escala = Math.min((W - 2 * margemX) / L, (H - 2 * margemY) / Math.max(Lw, 0.001));

    var x0 = margemX;                      // primeiro conector
    var x1 = x0 + L * escala;              // ultimo conector
    var meio = H / 2;
    var meiaAbertura = (Lw * escala) / 2;
    var meiaGramp = (ent.s * escala) / 2;

    var p = [];
    p.push('<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="none"/>');

    // zona de Whitmore (trapezio: comeca com o gramp s e abre a 30 graus)
    p.push('<path d="M ' + x0 + ' ' + (meio - meiaGramp) +
           ' L ' + x1 + ' ' + (meio - meiaAbertura) +
           ' L ' + x1 + ' ' + (meio + meiaAbertura) +
           ' L ' + x0 + ' ' + (meio + meiaGramp) + ' Z"' +
           ' fill="' + corVerde + '" fill-opacity="0.12" stroke="' + corVerde +
           '" stroke-width="1.6"/>');

    // linha de conectores
    p.push('<line x1="' + x0 + '" y1="' + meio + '" x2="' + x1 + '" y2="' + meio +
           '" stroke="' + corLinha + '" stroke-width="2.4"/>');

    var n = 6;
    for (var i = 0; i < n; i++) {
      var x = x0 + (x1 - x0) * (i / (n - 1));
      p.push('<circle cx="' + x.toFixed(1) + '" cy="' + meio + '" r="3.6" fill="' +
             corLinha + '" stroke="#fff" stroke-width="1.1"/>');
    }

    // cota de L
    var yL = H - 18;
    p.push(seta(x0, yL, x1, yL, corTexto));
    p.push(texto((x0 + x1) / 2, yL - 7, "L = " + fmt(ent.L, 1) + " in", corTexto, "middle"));

    // cota de Lw
    var xLw = x1 + 26;
    p.push(seta(xLw, meio - meiaAbertura, xLw, meio + meiaAbertura, corAcento));
    p.push(texto(xLw + 7, meio - 4, "Lw", corAcento, "start", 700));
    p.push(texto(xLw + 7, meio + 11, fmt(Lw, 2) + " in", corAcento, "start"));

    // angulo de 30 graus
    var raio = Math.min(46, (x1 - x0) * 0.42);
    var ang = 30 * Math.PI / 180;
    p.push('<path d="M ' + (x0 + raio) + ' ' + meio +
           ' A ' + raio + ' ' + raio + ' 0 0 0 ' +
           (x0 + raio * Math.cos(ang)).toFixed(1) + ' ' +
           (meio - raio * Math.sin(ang)).toFixed(1) + '"' +
           ' fill="none" stroke="' + corVerde + '" stroke-width="1.3"/>');
    p.push(texto(x0 + raio + 6, meio - 9, "30°", corVerde, "start", 650));

    demo.svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    demo.svg.innerHTML = p.join("");
  }

  function seta(x1, y1, x2, y2, cor) {
    var t = 4;
    var horizontal = Math.abs(y2 - y1) < 0.5;
    var marcas = horizontal
      ? '<line x1="' + x1 + '" y1="' + (y1 - t) + '" x2="' + x1 + '" y2="' + (y1 + t) + '" stroke="' + cor + '" stroke-width="1.2"/>' +
        '<line x1="' + x2 + '" y1="' + (y2 - t) + '" x2="' + x2 + '" y2="' + (y2 + t) + '" stroke="' + cor + '" stroke-width="1.2"/>'
      : '<line x1="' + (x1 - t) + '" y1="' + y1 + '" x2="' + (x1 + t) + '" y2="' + y1 + '" stroke="' + cor + '" stroke-width="1.2"/>' +
        '<line x1="' + (x2 - t) + '" y1="' + y2 + '" x2="' + (x2 + t) + '" y2="' + y2 + '" stroke="' + cor + '" stroke-width="1.2"/>';
    return '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 +
           '" stroke="' + cor + '" stroke-width="1.2"/>' + marcas;
  }

  function texto(x, y, conteudo, cor, ancora, peso) {
    return '<text x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" fill="' + cor +
           '" font-size="12" font-family="ui-monospace, Consolas, monospace"' +
           ' text-anchor="' + (ancora || "start") + '"' +
           ' font-weight="' + (peso || 500) + '">' + conteudo + "</text>";
  }

  /* ------------------------------------------------------------------ boot */

  function iniciar() {
    iniciarTema();
    iniciarCabecalho();
    iniciarScrollSpy();
    iniciarReveal();
    iniciarAbas();
    iniciarLightbox();
    iniciarDemo();

    var ano = $("#ano");
    if (ano) ano.textContent = new Date().getFullYear();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
