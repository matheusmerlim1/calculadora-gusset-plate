# Calculadora de Chapa de Nó (Gusset Plate)

Ferramenta desktop (Windows) para dimensionamento e verificação de chapas de
nó (gusset plates) em ligações de contraventamento diagonal, cobrindo a
seção de Whitmore, pseudo-colunas de Thornton, HSS circular (shear lag) e o
Método das Forças Uniformes (UFM).

Este material tem finalidade de estudo e apoio ao cálculo. Os resultados
devem sempre ser conferidos por um engenheiro estrutural habilitado.

## Download

Baixe o executável pronto (não precisa instalar Python) na
[página do projeto](https://matheusmerlim1.github.io/calculadora-gusset-plate/) ou
direto pela [última release](https://github.com/matheusmerlim1/calculadora-gusset-plate/releases/latest).

## Funcionalidades

- **Geometria (Whitmore)**: largura e área de Whitmore, verificação se a
  seção ultrapassa as bordas da chapa, comprimentos de pseudo-coluna L1/L2/L3
  (método de Thornton), incluindo interfaces não ortogonais — Chambers &
  Bartley (2007).
- **Material / Carga**: escoamento por tração, flambagem por compressão e
  bloco de cisalhamento equivalente na seção de Whitmore (AISC 360 / AISC
  Manual).
- **HSS circular**: fator de retardo de cisalhamento (shear lag) para
  conexões de HSS circular fendido soldado à chapa — Cheng & Kulak (2000).
- **UFM — Diagonal HSS/WF**: Método das Forças Uniformes completo, incluindo
  dimensionamento da chapa, solda de filete, parafusos e plastificação da
  parede de coluna HSS (AISC Design Guide 24) — Packer & Richardson (2025).
- Seletor de unidades (Imperial/Métrico), diagramas de referência para cada
  aba e exportação de relatório em PDF.

Um relatório técnico completo (`Chapas_de_No_Gusset_Plates_Relatorio_Tecnico.pdf`)
com a teoria, as fórmulas e a validação numérica acompanha este repositório.

## Observação importante sobre validação

A aba UFM foi validada contra o exemplo do Steel Tube Institute (Packer &
Richardson, 2025) com boa concordância geral. Uma única verificação
(plastificação da parede da coluna HSS, no caso de menor comprimento de
contato) apresenta uma diferença não totalmente esclarecida em relação ao
valor publicado no artigo — recomenda-se conferir manualmente esse caso
específico contra o AISC Design Guide 24 antes de uso em projeto (ver
`tests/test_ufm_calc.py`, que documenta o comportamento atual como teste de
regressão, e `LEIA-ME.txt` para mais detalhes).

## Estrutura

```text
.
|-- .github/workflows/
|   |-- secret-scan.yml
|   `-- ci.yml
|-- src/
|   |-- gusset_app.py     # interface grafica (Tkinter + Matplotlib)
|   |-- gusset_calc.py    # motor de calculo: Whitmore + pseudo-colunas + HSS circular
|   `-- ufm_calc.py       # motor de calculo: Metodo das Forcas Uniformes (UFM)
|-- tests/
|   |-- test_gusset_calc.py     # geometria: Exemplo 1 de Chambers & Bartley
|   |-- test_ufm_calc.py        # UFM: regressao do exemplo do Steel Tube Institute
|   |-- test_whitmore_js.mjs    # o porte JS bate com o motor Python?
|   `-- fixtures_whitmore.json  # valores de referencia gerados pelo Python
|-- tools/
|   `-- gen_js_fixtures.py    # regenera as fixtures a partir de gusset_calc.py
|-- index.html                # pagina do projeto (GitHub Pages)
|-- css/site.css              # estilo da pagina
|-- js/whitmore.js            # porte JS da secao de Whitmore, usado na demo ao vivo
|-- js/site.js                # abas, tema, lightbox e a demo da pagina
|-- img/                      # capturas de tela e diagramas usados na pagina
|-- conftest.py               # poe src/ no sys.path para os testes
|-- LEIA-ME.txt               # instrucoes de uso do executavel
|-- Chapas_de_No_Gusset_Plates_Relatorio_Tecnico.pdf
|-- requirements.txt          # dependencias de runtime
|-- requirements-dev.txt      # + pytest, para rodar os testes
|-- requirements-build.txt    # + pyinstaller, para gerar o .exe
`-- .gitignore
```

## A pagina do projeto

`index.html` publica em GitHub Pages uma pagina com capturas de tela do
programa, a explicacao de cada aba e uma demonstracao ao vivo da secao de
Whitmore que roda no navegador.

Essa demonstracao nao reimplementa o calculo por conta propria: `js/whitmore.js`
e um porte fiel do trecho correspondente de `src/gusset_calc.py`, e
`tests/test_whitmore_js.mjs` compara os dois contra os valores de
`tests/fixtures_whitmore.json` exigindo concordancia ate a ultima casa do
double. Se uma das duas implementacoes mudar sozinha, a CI falha.

```bash
node --test tests/test_whitmore_js.mjs   # roda a comparacao
python tools/gen_js_fixtures.py          # regenera as fixtures pelo motor Python
```

`CalculadoraGussetPlate.exe` é artefato de build e fica fora do controle de
versão (`.gitignore`). Os PDFs de artigos publicados de terceiros e a
planilha de referência também ficam fora do repositório (direitos autorais).

## Desenvolvimento

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
node --test tests/test_whitmore_js.mjs
python src\gusset_app.py
```

## Build do executável (Windows)

```powershell
python -m pip install -r requirements-build.txt
pyinstaller --onefile --windowed --name CalculadoraGussetPlate src\gusset_app.py
```

O executável gerado fica em `dist\CalculadoraGussetPlate.exe`.

## Referências

- Chambers, J.J. & Bartley, T.C. (2007) "Geometric Formulas for Gusset Plate
  Design", Engineering Journal, AISC, 3Q/2007 (+ errata 1Q/2008).
- Thornton, W.A. & Lini, C. (2011) "The Whitmore Section", Modern Steel
  Construction, AISC, julho/2011.
- Cheng, J.J.R. & Kulak, G.L. (2000) "Gusset Plate Connection to Round HSS
  Tension Members", Engineering Journal, AISC, 4Q/2000.
- Packer, J. & Richardson, S. (2025) "HSS Brace Connections to HSS Columns
  and WF Beams", Steel Tube Institute.
- Packer, J.A. & Olson, K. (2024) "Hollow Structural Section Connections",
  AISC Design Guide 24, 2ª ed.
