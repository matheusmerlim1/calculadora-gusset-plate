/*
 * whitmore.js
 * ===========
 * Porte em JavaScript do trecho do motor de calculo (src/gusset_calc.py)
 * usado pela demonstracao ao vivo da pagina: largura da secao de Whitmore,
 * escoamento a tracao e flambagem da pseudo-coluna de Thornton.
 *
 * As formulas seguem exatamente compute_geometry() e strength_checks(),
 * inclusive nos casos degenerados (KL/r <= 0). A equivalencia numerica com
 * o motor Python e verificada por tests/test_whitmore_js.mjs contra os
 * valores de tests/fixtures_whitmore.json, gerados por
 * tools/gen_js_fixtures.py a partir do proprio gusset_calc.py.
 *
 * Unidades imperiais: in, ksi, kips.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.Whitmore = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var TAN30 = Math.tan(30 * Math.PI / 180);

  /* Largura de Whitmore: espalhamento a 30 graus a partir do primeiro
     conector, somado ao espacamento perpendicular entre linhas (gramp).
     gusset_calc.py, linha 152: Lw = 2 * L * tan(30) + s */
  function whitmoreWidth(L, s) {
    return 2 * L * TAN30 + s;
  }

  /* Tensao critica de flambagem - AISC 360 Capitulo E.
     Reproduz o ramo "KL_r > 0 ? pi^2 E / KL_r^2 : infinito" do Python, que
     faz Fcr cair para Fy quando a pseudo-coluna nao se desenvolve. */
  function criticalStress(KL_r, Fy, E) {
    var Fe = KL_r > 0 ? (Math.PI * Math.PI * E) / (KL_r * KL_r) : Infinity;
    if (KL_r <= 4.71 * Math.sqrt(E / Fy)) {
      return Math.pow(0.658, Fy / Fe) * Fy;
    }
    return 0.877 * Fe;
  }

  /* Verificacao completa da secao de Whitmore.
     Recebe: L, s, tp, Fy, E, K, Lc (comprimento de pseudo-coluna),
             phi_y, phi_c e Pu (carga fatorada na diagonal). */
  function check(inp) {
    var L = num(inp.L), s = num(inp.s), tp = num(inp.tp);
    var Fy = num(inp.Fy), E = num(inp.E), K = num(inp.K), Lc = num(inp.Lc);
    var phi_y = inp.phi_y === undefined ? 0.9 : num(inp.phi_y);
    var phi_c = inp.phi_c === undefined ? 0.9 : num(inp.phi_c);
    var Pu = num(inp.Pu);

    var Lw = whitmoreWidth(L, s);
    var Aw = Lw * tp;

    var Pn_yield = Fy * Aw;
    var phiPn_yield = phi_y * Pn_yield;

    var r = tp / Math.sqrt(12);                 // raio de giracao da chapa
    var KL_r = r > 0 ? (K * Lc) / r : 0;
    var Fcr = criticalStress(KL_r, Fy, E);

    var Pn_buckling = Fcr * Aw;
    var phiPn_buckling = phi_c * Pn_buckling;

    return {
      Lw: Lw,
      Aw: Aw,
      r: r,
      KL_r: KL_r,
      Fcr: Fcr,
      phiPn_yield: phiPn_yield,
      phiPn_buckling: phiPn_buckling,
      governing: Math.min(phiPn_yield, phiPn_buckling),
      DCR_yield: phiPn_yield > 0 ? Pu / phiPn_yield : Infinity,
      DCR_buckling: phiPn_buckling > 0 ? Pu / phiPn_buckling : Infinity
    };
  }

  function num(v) {
    var x = typeof v === "number" ? v : parseFloat(v);
    return isFinite(x) ? x : 0;
  }

  return {
    TAN30: TAN30,
    whitmoreWidth: whitmoreWidth,
    criticalStress: criticalStress,
    check: check
  };
});
