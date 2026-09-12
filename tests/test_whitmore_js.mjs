/*
 * Verifica se o porte em JavaScript usado pela demonstracao ao vivo da
 * pagina (js/whitmore.js) reproduz os mesmos numeros do motor Python
 * (src/gusset_calc.py).
 *
 * Os valores de referencia em fixtures_whitmore.json sao gerados por
 * tools/gen_js_fixtures.py. Se a formula mudar de um lado so, este teste
 * falha e aponta qual grandeza divergiu.
 *
 * Uso:  node --test tests/
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const AQUI = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const Whitmore = require(join(AQUI, "..", "js", "whitmore.js"));
const casos = JSON.parse(readFileSync(join(AQUI, "fixtures_whitmore.json"), "utf8"));

/* Tolerancia relativa: o Python serializa em double, entao a unica
   diferenca admissivel e o arredondamento da ultima casa binaria. */
const REL = 1e-12;

function perto(obtido, esperado, rotulo) {
  if (esperado === 0) {
    assert.ok(Math.abs(obtido) < 1e-12, `${rotulo}: ${obtido} != 0`);
    return;
  }
  const erro = Math.abs(obtido - esperado) / Math.abs(esperado);
  assert.ok(erro < REL, `${rotulo}: ${obtido} != ${esperado} (erro rel. ${erro})`);
}

const GRANDEZAS = [
  "Lw", "Aw", "r", "KL_r", "Fcr",
  "phiPn_yield", "phiPn_buckling", "governing",
  "DCR_yield", "DCR_buckling",
];

test("fixtures existem e cobrem os ramos de flambagem", () => {
  assert.ok(casos.length >= 6, "esperado ao menos 6 casos de referencia");
  assert.ok(casos.some((c) => c.entrada.Lc === 0), "falta o caso de pseudo-coluna nula");
  assert.ok(
    casos.some((c) => c.KL_r > 4.71 * Math.sqrt(c.entrada.E / c.entrada.Fy)),
    "falta um caso no ramo elastico (coluna esbelta)",
  );
});

for (const [i, caso] of casos.entries()) {
  const { L, s, tp, Fy, K, E, Lc, Pu } = caso.entrada;
  test(`caso ${i + 1}: L=${L} s=${s} tp=${tp} Fy=${Fy} Lc=${Lc}`, () => {
    const obtido = Whitmore.check({ L, s, tp, Fy, E, K, Lc, Pu, phi_y: 0.9, phi_c: 0.9 });
    for (const g of GRANDEZAS) {
      perto(obtido[g], caso[g], g);
    }
  });
}

test("largura de Whitmore e o espalhamento a 30 graus mais o gramp", () => {
  perto(Whitmore.whitmoreWidth(10, 0), 2 * 10 * Math.tan(Math.PI / 6), "Lw sem gramp");
  perto(Whitmore.whitmoreWidth(10, 3) - Whitmore.whitmoreWidth(10, 0), 3, "efeito do gramp");
  assert.equal(Whitmore.whitmoreWidth(0, 4), 4, "sem linha de parafusos sobra so o gramp");
});

test("pseudo-coluna nula nao reduz a resistencia a compressao", () => {
  const r = Whitmore.check({ L: 13, s: 3, tp: 0.5, Fy: 50, E: 29000, K: 0.5, Lc: 0, Pu: 127 });
  perto(r.Fcr, 50, "Fcr deve cair para Fy quando KL/r = 0");
  perto(r.phiPn_buckling, r.phiPn_yield, "sem esbeltez, flambagem iguala escoamento");
});

test("entradas invalidas viram zero em vez de NaN", () => {
  const r = Whitmore.check({ L: "", s: "abc", tp: 0.5, Fy: 50, E: 29000, K: 1, Lc: 5, Pu: 0 });
  assert.ok(Number.isFinite(r.Lw), "Lw deve continuar finito");
  assert.equal(r.Lw, 0, "L e s invalidos zeram a largura");
});
