"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = (v, casas = 1) => (v == null ? "—" : (v * 100).toFixed(casas).replace(".", ",") + "%");
const num = (v, casas = 3) => (v == null ? "—" : Number(v).toFixed(casas).replace(".", ","));

const estado = { info: null, exec: null, pagina: 0, limiar: 0.8, foco: null };

// ---------------------------------------------------------------- início
async function iniciar() {
  try {
    const r = await fetch("/api/info");
    estado.info = await r.json();
    const v = estado.info.versoes;
    $("#versoes").textContent = `PaddleOCR ${v.paddleocr} · Paddle ${v.paddlepaddle} · ${estado.info.parametros_paddleocr.device.toUpperCase()}`;
    const sel = $("#perfil");
    for (const [nome, etapas] of Object.entries(estado.info.perfis)) {
      sel.add(new Option(nome, nome));
    }
    sel.onchange = () => {
      const et = estado.info.perfis[sel.value];
      $("#etapas").textContent = et.length ? "Etapas: " + et.join(" → ") : "Imagem enviada sem alterações.";
    };
    sel.onchange();
  } catch (e) {
    $("#versoes").textContent = "servidor indisponível";
  }
  carregarHistorico();
}

async function carregarHistorico() {
  const lista = await (await fetch("/api/execucoes")).json();
  const ul = $("#historico");
  ul.innerHTML = lista.length ? "" : '<li class="vazio">Nenhuma execução ainda.</li>';
  for (const e of lista) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${esc(e.arquivo)} <small>· ${esc(e.perfil)}</small></span><small>${esc(e.criado_em.replace("T", " "))}</small>`;
    li.onclick = async () => mostrar(await (await fetch(`/api/execucoes/${e.id}`)).json());
    ul.appendChild(li);
  }
}

// ---------------------------------------------------------------- envio
const inputArq = $("#arquivo");
const drop = $("#drop");
inputArq.onchange = () => selecionar(inputArq.files[0]);
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("sobre"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("sobre"); }));
drop.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) { const dt = new DataTransfer(); dt.items.add(f); inputArq.files = dt.files; selecionar(f); }
});
function selecionar(f) {
  $("#nome-arquivo").textContent = f ? `${f.name} (${(f.size / 1024).toFixed(0)} KB)` : "";
  $("#botao").disabled = !f;
}
$("#limiar").oninput = (e) => ($("#limiar-valor").textContent = Number(e.target.value).toFixed(2).replace(".", ","));

$("#form").onsubmit = async (e) => {
  e.preventDefault();
  const f = inputArq.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("arquivo", f);
  fd.append("perfil", $("#perfil").value);
  fd.append("limiar", $("#limiar").value);
  fd.append("detectar_colunas", $("#colunas").checked);
  fd.append("referencia", $("#referencia-envio").value);
  fd.append("corrigir", $("#corrigir").checked);
  const st = $("#status");
  st.className = "status";
  $("#botao").disabled = true;
  const t0 = performance.now();
  const relogio = setInterval(() => (st.textContent = `Reconhecendo… ${((performance.now() - t0) / 1000).toFixed(0)} s (CPU; páginas grandes podem levar mais de 30 s)`), 500);
  try {
    const r = await fetch("/api/ocr", { method: "POST", body: fd });
    const corpo = await r.json();
    if (!r.ok) throw new Error(corpo.detail || r.statusText);
    st.textContent = `Concluído em ${((performance.now() - t0) / 1000).toFixed(1)} s.`;
    mostrar(corpo);
    carregarHistorico();
  } catch (err) {
    st.className = "status erro";
    st.textContent = "Erro: " + err.message;
  } finally {
    clearInterval(relogio);
    $("#botao").disabled = false;
  }
};

// ---------------------------------------------------------------- resultado
function mostrar(exec, manterPagina = false) {
  estado.exec = exec;
  estado.limiar = exec.limiar;
  if (!manterPagina) estado.pagina = 0;
  $("#resultado").hidden = false;
  $("#titulo-resultado").textContent = exec.arquivo;
  $("#sub-resultado").textContent =
    `perfil “${exec.perfil}” · limiar ${num(exec.limiar, 2)} · ${exec.detectar_colunas ? "detecção de colunas ligada" : "uma coluna"} · ${exec.criado_em.replace("T", " ")} · execução ${exec.id}`;
  const d = exec.downloads;
  $("#downloads").innerHTML =
    `<a href="${d.pacote_json}">⬇ JSON completo</a><a href="${d.documento_txt}" download>⬇ Texto (.txt)</a>` +
    (exec.metadados ? `<a href="${d.metadados_json}" download>⬇ metadados.json</a>` : "");
  cardsDocumento();
  const abas = $("#abas-paginas");
  abas.innerHTML = "";
  abas.hidden = exec.paginas.length < 2;
  exec.paginas.forEach((p, i) => {
    const b = document.createElement("button");
    b.textContent = `Página ${p.pagina}` + (p.status !== "ok" ? " ⚠" : "");
    b.onclick = () => { estado.pagina = i; renderPagina(); };
    abas.appendChild(b);
  });
  renderPagina();
  renderMetadados();
  if (!manterPagina) $("#resultado").scrollIntoView({ behavior: "smooth" });
}

function card(rotulo, valor, nota = "", classe = "") {
  return `<div class="card ${classe}"><div class="rotulo">${rotulo}</div><div class="valor">${valor}</div><div class="nota">${nota}</div></div>`;
}

function cardsDocumento() {
  const d = estado.exec.documento;
  let h = "";
  if (d.acuracia_caracteres != null) {
    h += card("Acurácia de caracteres", pct(d.acuracia_caracteres), `CER ${num(d.cer, 4)} · ${d.paginas_avaliadas_com_referencia} pág. com referência`, "real destaque");
    h += card("Acurácia de palavras", pct(d.acuracia_palavras), `WER ${num(d.wer, 4)}`, "real destaque");
  }
  if (d.acuracia_caracteres_corrigido != null) {
    h += card("Acurácia após correção", pct(d.acuracia_caracteres_corrigido), `caracteres · antes ${pct(d.acuracia_caracteres)}`, "real destaque");
    h += card("Palavras após correção", pct(d.acuracia_palavras_corrigido), `antes ${pct(d.acuracia_palavras)}`, "real destaque");
  }
  if (d.correcoes_aplicadas || d.correcoes_sugeridas)
    h += card("Correções", d.correcoes_aplicadas, `aplicadas · ${d.correcoes_sugeridas} sugestões para revisar`);
  h += card("Confiança média", pct(d.confianca_media), `${d.fragmentos} trechos detectados`, "estimativa");
  h += card("Trechos para revisão", d.trechos_para_revisao, `limiar ${num(estado.exec.limiar, 2)} + sinais de ambiguidade`);
  h += card("Palavras / caracteres", `${d.palavras}`, `${d.caracteres} caracteres`);
  h += card("Páginas", d.paginas, d.paginas_com_erro ? `${d.paginas_com_erro} com erro` : "todas processadas");
  h += card("Tempo de OCR", `${num(d.tempo_ocr_total_s, 1)} s`, "CPU, sem pré-processamento");
  if (d.acuracia_caracteres == null)
    h += card("Acurácia real", "—", "informe o texto de referência na aba Acurácia");
  $("#cards-documento").innerHTML = h;
}

const pag = () => estado.exec.paginas[estado.pagina];
const classeConf = (c) => (c == null ? "baixa" : c >= 0.95 ? "alta" : c >= estado.limiar ? "media" : "baixa");

function renderPagina() {
  $$("#abas-paginas button").forEach((b, i) => b.classList.toggle("ativa", i === estado.pagina));
  const p = pag();
  if (p.status !== "ok") {
    $("#texto").innerHTML = `<p class="pend">Página não processada: ${esc(p.erro)}</p>`;
    $("#imagem").removeAttribute("src");
    $("#sobreposicao").innerHTML = "";
    return;
  }
  renderVisual(p);
  renderMetricas(p);
  renderAcuracia(p);
  renderJson("pagina");
}

// ---------------------------------------------------------------- visualização
function renderVisual(p) {
  const img = $("#imagem");
  img.src = p.imagem_url;
  const { largura, altura } = p.dimensoes_imagem;
  const svg = $("#sobreposicao");
  svg.setAttribute("viewBox", `0 0 ${largura} ${altura}`);
  svg.setAttribute("preserveAspectRatio", "none");
  let caixas = "", ordem = "", n = 0;
  const texto = $("#texto");
  texto.innerHTML = "";
  p.linhas_ordenadas.forEach((linha, li) => {
    const div = document.createElement("div");
    div.className = "linha-ocr";
    div.innerHTML = `<span class="n">${li + 1}</span>`;
    const conteudo = document.createElement("span");
    linha.forEach((f, k) => {
      const [x1, y1, x2, y2] = f.caixa;
      const cl = classeConf(f.confianca);
      n += 1;
      caixas += `<rect class="caixa-ocr ${cl}" data-i="${f.indice_paddleocr}" x="${x1}" y="${y1}" width="${x2 - x1}" height="${y2 - y1}"></rect>`;
      ordem += `<text class="ordem" x="${x1 + 2}" y="${y1 + 14}">${n}</text>`;
      const s = document.createElement("span");
      s.className = `frag ${cl}`;
      s.dataset.i = f.indice_paddleocr;
      s.title = `confiança ${num(f.confianca, 4)}`;
      s.textContent = f.texto;
      conteudo.appendChild(s);
      if (k < linha.length - 1) conteudo.appendChild(document.createTextNode(" "));
    });
    div.appendChild(conteudo);
    texto.appendChild(div);
  });
  svg.innerHTML = `<g id="g-caixas">${caixas}</g><g id="g-ordem">${ordem}</g>`;
  aplicarCamadas();
  const modo = $("#modo-texto");
  modo.hidden = !p.correcao;
  $("#titulo-texto").innerHTML = p.correcao && modo.value === "corrigido"
    ? 'Texto corrigido <small>(<span class="cor-aplicada">aplicada</span> · <span class="cor-sugestao">sugestão</span> — passe o mouse)</small>'
    : 'Texto reconhecido <small>(bruto do modelo, sem correções)</small>';
  if (p.correcao && modo.value === "corrigido") renderCorrigido(p);
}

function renderCorrigido(p) {
  const porLinha = {};
  for (const c of p.correcao.correcoes) (porLinha[c.linha] ||= []).push(c);
  const linhas = p.texto.split("\n");
  $("#texto").innerHTML = linhas.map((l, i) => {
    let h = "", pos = 0;
    for (const c of (porLinha[i + 1] || []).sort((a, b) => a.inicio - b.inicio)) {
      if (c.inicio < pos) continue;
      h += esc(l.slice(pos, c.inicio));
      const dica = esc(`${c.original} → ${c.sugestao ?? "(sem sugestão)"} · ${c.metodo} · confiança ${c.confianca}\n${c.motivo}`);
      h += c.aplicada ? `<span class="cor-aplicada" title="${dica}">${esc(c.sugestao)}</span>`
                      : `<span class="cor-sugestao" title="${dica}">${esc(c.original)}</span>`;
      pos = c.fim;
    }
    h += esc(l.slice(pos));
    return `<div class="linha-ocr"><span class="n">${i + 1}</span><span>${h}</span></div>`;
  }).join("");
}
$("#modo-texto").onchange = () => renderVisual(pag());

function aplicarCamadas() {
  const gc = $("#g-caixas"), go = $("#g-ordem");
  if (gc) gc.style.display = $("#mostrar-caixas").checked ? "" : "none";
  if (go) go.style.display = $("#mostrar-ordem").checked ? "" : "none";
}
$("#mostrar-caixas").onchange = aplicarCamadas;
$("#mostrar-ordem").onchange = aplicarCamadas;

function fragmento(i) {
  for (const l of pag().linhas_ordenadas) for (const f of l) if (String(f.indice_paddleocr) === String(i)) return f;
  return null;
}
function focar(i, rolar) {
  $$(".foco").forEach((e) => e.classList.remove("foco"));
  if (i == null) return;
  $$(`[data-i="${i}"]`).forEach((e) => e.classList.add("foco"));
  if (rolar) {
    const alvo = rolar === "texto" ? $(`.frag[data-i="${i}"]`) : $(`rect[data-i="${i}"]`);
    alvo?.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}
const dica = $("#dica");
$("#sobreposicao").addEventListener("mousemove", (e) => {
  const r = e.target.closest("rect");
  if (!r) { dica.hidden = true; focar(null); return; }
  const f = fragmento(r.dataset.i);
  focar(r.dataset.i);
  const box = $("#imagem-wrap").getBoundingClientRect();
  dica.hidden = false;
  dica.innerHTML = `${esc(f.texto)}<br><small>confiança ${num(f.confianca, 4)}</small>`;
  dica.style.left = Math.min(e.clientX - box.left + 12, box.width - 260) + "px";
  dica.style.top = e.clientY - box.top + 14 + "px";
});
$("#sobreposicao").addEventListener("mouseleave", () => { dica.hidden = true; focar(null); });
$("#sobreposicao").addEventListener("click", (e) => { const r = e.target.closest("rect"); if (r) focar(r.dataset.i, "texto"); });
$("#texto").addEventListener("mouseover", (e) => { const s = e.target.closest(".frag"); if (s) focar(s.dataset.i); });
$("#texto").addEventListener("click", (e) => { const s = e.target.closest(".frag"); if (s) focar(s.dataset.i, "imagem"); });
$("#copiar").onclick = () => navigator.clipboard.writeText(
  pag().correcao && $("#modo-texto").value === "corrigido" ? pag().correcao.texto_corrigido : pag().texto);

// ---------------------------------------------------------------- métricas
function renderMetricas(p) {
  const m = p.metricas_confianca;
  $("#cards-confianca").innerHTML =
    card("Confiança média", pct(m.confianca_media), "média simples por trecho", "estimativa") +
    card("Ponderada por caracteres", pct(m.confianca_ponderada_por_caracteres), "trechos longos pesam mais", "estimativa") +
    card("Mediana / mínima", `${pct(m.confianca_mediana)}`, `mínima ${pct(m.confianca_minima)}`, "estimativa") +
    card("Trechos ≥ limiar", pct(m.percentual_fragmentos_acima_do_limiar), `${m.fragmentos_acima_do_limiar} de ${m.fragmentos}`, "estimativa") +
    card("Caracteres ≥ limiar", pct(m.percentual_caracteres_acima_do_limiar), `limiar ${num(m.limiar, 2)}`, "estimativa") +
    card("Para revisão humana", m.trechos_para_revisao, "baixa confiança ou caracteres ambíguos");
  $("#histograma").innerHTML = histograma(m.histograma, m.limiar);
  const lay = p.layout || {};
  $("#tabela-tempo").innerHTML = [
    ["Pré-processamento", `${num(p.tempo_preprocessamento_s, 3)} s (${p.etapas_preprocessamento.length ? p.etapas_preprocessamento.join(" → ") : "nenhum"})`],
    ["OCR (detecção + reconhecimento)", `${num(p.tempo_ocr_s, 3)} s`],
    ["Dimensões da imagem no OCR", `${p.dimensoes_imagem.largura} × ${p.dimensoes_imagem.altura} px`],
    ["Colunas detectadas", lay.colunas ?? "—"],
    ["Trechos / linhas", `${p.quantidade_fragmentos} / ${p.linhas_ordenadas.length}`],
    ["Palavras / caracteres", `${p.quantidade_palavras} / ${p.quantidade_caracteres}`],
  ].map(([a, b]) => `<tr><th>${a}</th><td>${esc(b)}</td></tr>`).join("");

  const cx = $("#caixa-correcoes");
  cx.hidden = !p.correcao;
  if (p.correcao) {
    const cs = p.correcao.correcoes;
    $("#n-correcoes").textContent = `${p.correcao.estatisticas.aplicadas} aplicadas · ${p.correcao.estatisticas.sugestoes} sugestões`;
    $("#tabela-correcoes").innerHTML = "<tr><th>Linha</th><th>Original</th><th>Correção</th><th>Status</th><th>Método</th><th>Conf.</th><th>Motivo</th></tr>" +
      cs.map((c) => `<tr><td>${c.linha}</td><td><code>${esc(c.original)}</code></td><td><code>${esc(c.sugestao ?? "—")}</code></td><td>${c.aplicada ? "aplicada" : "sugestão"}</td><td>${esc(c.metodo)}</td><td class="num">${num(c.confianca, 2)}</td><td><small>${esc(c.motivo)}</small></td></tr>`).join("");
  }
  const rev = p.revisao_humana || [];
  $("#n-revisao").textContent = rev.length;
  $("#lista-revisao").innerHTML = rev.length
    ? rev.map((r) => `<li data-i="${r.indice_paddleocr}"><code>${esc(r.texto_bruto)}</code><small>linha ${r.linha_txt} · confiança ${num(r.confianca, 3)} · ${esc(r.motivos.join("; "))}</small></li>`).join("")
    : '<li class="vazio" style="border:0">Nenhum trecho marcado.</li>';
  $$("#lista-revisao li[data-i]").forEach((li) => (li.onclick = () => { trocarAba("visual"); focar(li.dataset.i, "texto"); }));

  const el = p.elementos_juridicos || {};
  const nomes = { artigos: "Artigos", paragrafos: "Parágrafos", incisos: "Incisos", alineas: "Alíneas", leis: "Leis citadas", datas: "Datas" };
  $("#elementos").innerHTML = Object.entries(nomes).map(([k, n]) => {
    const itens = el[k] || [];
    return `<div><b>${n}</b> <span class="chip">${itens.length}</span><div class="chips">${itens.slice(0, 40).map((i) => `<span>${esc(i)}</span>`).join("") || '<span class="vazio" style="border:0">nenhum</span>'}</div></div>`;
  }).join("");
}

function histograma(h, limiar) {
  const W = 460, H = 190, m = { e: 30, d: 8, t: 10, b: 30 };
  const max = Math.max(1, ...h.map((b) => b.quantidade));
  const bw = (W - m.e - m.d) / h.length;
  let s = `<svg class="histo" viewBox="0 0 ${W} ${H}" role="img" aria-label="Histograma de confiança">`;
  h.forEach((b, i) => {
    const alt = ((H - m.t - m.b) * b.quantidade) / max;
    const x = m.e + i * bw, y = H - m.b - alt;
    s += `<rect class="barra ${b.ate <= limiar ? "abaixo" : ""}" x="${x + 2}" y="${y}" width="${bw - 4}" height="${alt}" rx="2"><title>${b.de}–${b.ate}: ${b.quantidade} trechos</title></rect>`;
    if (b.quantidade) s += `<text x="${x + bw / 2}" y="${y - 3}" text-anchor="middle">${b.quantidade}</text>`;
    s += `<text x="${x}" y="${H - m.b + 14}" text-anchor="middle">${b.de.toFixed(1)}</text>`;
  });
  s += `<text x="${W - m.d}" y="${H - m.b + 14}" text-anchor="middle">1.0</text>`;
  const xl = m.e + limiar * (W - m.e - m.d);
  s += `<line class="limiar" x1="${xl}" x2="${xl}" y1="${m.t}" y2="${H - m.b}"></line><text x="${xl - 4}" y="${m.t + 10}" text-anchor="end">limiar ${limiar}</text>`;
  s += `<text x="${W / 2}" y="${H - 2}" text-anchor="middle">confiança do trecho</text></svg>`;
  return s;
}

// ---------------------------------------------------------------- acurácia
function renderAcuracia(p) {
  const ref = estado.exec.referencias?.[String(p.pagina)] || "";
  $("#referencia").value = ref;
  const m = p.metricas_referencia;
  const alvo = $("#resultado-acuracia");
  const auto = estado.exec.referencia_automatica && p.pagina === 1
    ? `<p class="aviso" style="border-color:var(--alta);background:var(--alta-bg)">Referência carregada automaticamente de <code>${esc(estado.exec.referencia_automatica)}</code> (texto oficial da camada de texto do PDF).</p>` : "";
  if (!m) { alvo.innerHTML = '<p class="vazio">Nenhuma referência para esta página ainda.</p>'; return; }
  if (m.erro) { alvo.innerHTML = `<p class="pend">${esc(m.erro)}</p>`; return; }
  const c = m.caracteres, w = m.palavras;
  const barra = (o) => {
    const t = Math.max(1, o.distancia);
    return `<div class="ops"><span style="width:${(100 * o.substituicoes) / t}%;background:var(--baixa)"></span><span style="width:${(100 * o.remocoes) / t}%;background:var(--media)"></span><span style="width:${(100 * o.insercoes) / t}%;background:var(--primaria)"></span></div>
      <small>${o.substituicoes} trocados · ${o.remocoes} faltando · ${o.insercoes} sobrando (total ${o.distancia})</small>`;
  };
  const nomes = { artigos: "Artigos (Art. Nº)", paragrafos: "Parágrafos (§)", incisos: "Incisos", alineas: "Alíneas", leis: "Leis citadas", datas: "Datas" };
  const linhasEl = Object.entries(m.elementos_juridicos).map(([k, v]) =>
    `<tr><td>${nomes[k] || k}</td><td class="num">${v.na_referencia}</td><td class="num">${v.preservados_no_ocr}</td><td class="num">${pct(v.taxa_preservacao)}</td><td>${v.ausentes_ou_divergentes.slice(0, 8).map((a) => `<code>${esc(a)}</code>`).join(" ")}</td></tr>`).join("");
  const diff = m.diff.map((t) => {
    if (t.tipo === "igual") return esc(t.referencia);
    if (t.tipo === "trocado") return `<span class="trocado"><del>${esc(t.referencia)}</del> <ins>${esc(t.ocr)}</ins></span>`;
    if (t.tipo === "faltou") return `<span class="faltou" title="estava na referência e não foi reconhecido">${esc(t.referencia)}</span>`;
    return `<span class="sobrou" title="reconhecido mas não existe na referência">${esc(t.ocr)}</span>`;
  }).join(" ");
  const mc = p.metricas_referencia_corrigido;
  const comparativo = mc ? `<div class="cards">
      ${card("Caracteres: bruto → corrigido", `${pct(m.acuracia_caracteres, 2)} → ${pct(mc.acuracia_caracteres, 2)}`, `CER ${num(m.cer, 4)} → ${num(mc.cer, 4)}`, "real destaque")}
      ${card("Palavras: bruto → corrigido", `${pct(m.acuracia_palavras, 2)} → ${pct(mc.acuracia_palavras, 2)}`, `WER ${num(m.wer, 4)} → ${num(mc.wer, 4)}`, "real destaque")}
    </div><p class="sub">Os detalhes abaixo se referem ao texto <b>bruto</b> do OCR.</p>` : "";
  alvo.innerHTML = `${auto}${comparativo}
    <div class="cards">
      ${card("Acurácia de caracteres", pct(m.acuracia_caracteres, 2), `CER ${num(m.cer, 4)}`, "real destaque")}
      ${card("Acurácia de palavras", pct(m.acuracia_palavras, 2), `WER ${num(m.wer, 4)}`, "real destaque")}
      ${card("Caracteres", c.referencia, `referência · OCR: ${c.ocr}`)}
      ${card("Palavras", w.referencia, `referência · OCR: ${w.ocr}`)}
    </div>
    <div class="grade-2">
      <div class="caixa"><h3>Erros de caractere</h3>${barra(c)}</div>
      <div class="caixa"><h3>Erros de palavra</h3>${barra(w)}</div>
    </div>
    <div class="caixa"><h3>Preservação de elementos jurídicos</h3>
      <table class="tabela"><tr><th>Elemento</th><th>Na referência</th><th>Idênticos no OCR</th><th>Taxa</th><th>Ausentes ou divergentes</th></tr>${linhasEl}</table>
      <small class="vazio">“Art. 4°” (grau) no lugar de “Art. 4º” (ordinal) conta como divergente.</small></div>
    <div class="caixa"><h3>Comparação palavra a palavra</h3>
      <p class="sub" style="margin-bottom:.5rem"><span class="diff"><span class="trocado"><del>referência</del> <ins>OCR</ins></span> trocado · <span class="faltou">faltou</span> · <span class="sobrou">sobrou</span></span></p>
      <div class="diff">${diff}</div></div>
    <small class="vazio">Normalização: ${esc(m.normalizacao)}.</small>`;
}

async function enviarReferencia(texto) {
  const p = pag();
  const r = await fetch(`/api/execucoes/${estado.exec.id}/referencia`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pagina: p.pagina, texto }),
  });
  const corpo = await r.json();
  if (!r.ok) { alert(corpo.detail || "erro"); return; }
  mostrar(corpo, true);
  trocarAba("acuracia");
}
$("#calcular").onclick = () => enviarReferencia($("#referencia").value);
$("#limpar-ref").onclick = () => enviarReferencia("");
$("#usar-ocr").onclick = () => { $("#referencia").value = pag().texto; $("#referencia").focus(); };

// ---------------------------------------------------------------- metadados
function renderMetadados() {
  const md = estado.exec.metadados;
  const alvo = $("#metadados");
  if (!md) { alvo.innerHTML = '<p class="vazio">Metadados não gerados para esta execução.</p>'; return; }
  const ids = md.norma?.identificacoes || [];
  const est = md.estatisticas || {};
  let h = `<p class="aviso">${esc(md.aviso)}</p><div class="cards">`;
  for (const [k, n] of [["artigos", "Artigos"], ["paragrafos", "Parágrafos"], ["incisos", "Incisos"], ["divisoes", "Títulos/capítulos"], ["artigos_com_revisao_humana", "Artigos c/ revisão"], ["pendencias", "Pendências"]])
    h += card(n, est[k] ?? "—");
  h += "</div><div class='grade-2'><div class='caixa'><h3>Identificação da norma</h3>";
  h += ids.length ? `<table class="tabela">${ids.map((i) => `<tr><td><code>${esc(i.texto_bruto)}</code><br><small>nº ${esc(i.numero_normalizado ?? "?")} · data ${esc(i.data_normalizada ?? "?")} · pág. ${i.pagina}</small>${(i.pendencias || []).map((x) => `<div class="pend">⚠ ${esc(x)}</div>`).join("")}</td></tr>`).join("")}</table>` : '<p class="vazio">Nenhuma identificação (LEI Nº …) reconhecida.</p>';
  const em = md.norma?.ementas || [];
  if (em.length) h += `<h3 style="margin-top:.8rem">Ementa</h3>${em.map((e) => `<p>${esc(e.texto_bruto || JSON.stringify(e))}</p>`).join("")}`;
  h += "</div><div class='caixa'><h3>Pendências</h3>";
  h += (md.pendencias || []).length ? `<ul class="lista-revisao">${md.pendencias.map((p) => `<li><b>${esc(p.onde)}</b><br><small>${esc(p.motivo)}</small></li>`).join("")}</ul>` : '<p class="vazio">Nenhuma.</p>';
  h += "</div></div><div class='caixa arvore'><h3>Estrutura e dispositivos</h3>";
  const disp = (d, rot) => {
    const filhos = ["paragrafos", "incisos", "alineas"].flatMap((k) => (d[k] || []).map((f) => disp(f, f.tipo === "paragrafo" ? (f.unico ? "Parágrafo único" : `§ ${f.rotulo_bruto}`) : f.tipo === "inciso" ? `${f.rotulo_bruto} –` : `${f.rotulo_bruto})`)));
    const alerta = (d.pendencias?.length || d.revisao_humana?.length) ? " ⚠" : "";
    const texto = d.texto_bruto || (d.linhas || []).join(" ") || "";
    return `<details><summary><b>${esc(rot)}</b>${alerta} ${esc(texto.slice(0, 140))}</summary>${(d.pendencias || []).map((x) => `<div class="pend">${esc(x)}</div>`).join("")}${filhos.join("")}</details>`;
  };
  h += (md.artigos || []).map((a) => disp(a, `Art. ${a.rotulo_bruto}`)).join("") || '<p class="vazio">Nenhum artigo reconhecido.</p>';
  h += "</div>";
  alvo.innerHTML = h;
}

// ---------------------------------------------------------------- JSON
async function renderJson(qual) {
  const pre = $("#json");
  const urls = { pagina: pag().json_url, pacote: estado.exec.downloads.pacote_json, metadados: estado.exec.downloads.metadados_json };
  pre.textContent = "carregando…";
  try {
    const dados = await (await fetch(urls[qual])).json();
    let txt = JSON.stringify(dados, null, 2);
    if (txt.length > 400000) txt = txt.slice(0, 400000) + "\n… (truncado na tela; use o botão de download)";
    pre.textContent = txt;
  } catch { pre.textContent = "indisponível"; }
}
$$("[data-json]").forEach((b) => (b.onclick = () => renderJson(b.dataset.json)));

// ---------------------------------------------------------------- abas
function trocarAba(nome) {
  $$(".abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === nome));
  $$(".aba").forEach((a) => (a.hidden = a.id !== `aba-${nome}`));
}
$$(".abas button").forEach((b) => (b.onclick = () => trocarAba(b.dataset.aba)));

iniciar();
