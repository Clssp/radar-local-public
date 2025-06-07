# ==============================================================================
# main.py - Radar Local v2.7 (Produção com xhtml2pdf e Supabase)
# ==============================================================================

import streamlit as st
import requests
from openai import OpenAI
from datetime import datetime
import base64
import pandas as pd
from io import BytesIO
import unicodedata
import re
import json
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
import numpy as np
import qrcode
from pathlib import Path
import psycopg2

# --- CONFIGURAÇÕES E INICIALIZAÇÃO ---
st.set_page_config(page_title="Radar Local", page_icon="📡", layout="wide")

try:
    API_KEY_GOOGLE = st.secrets["google"]["api_key"]
    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
except (KeyError, FileNotFoundError):
    st.error("As chaves de API (Google, OpenAI) não foram encontradas. Configure seu arquivo `secrets.toml`.")
    st.stop()

# --- FUNÇÕES DE BANCO DE DADOS E UTILIDADE ---
@st.cache_resource
def init_connection():
    """Inicializa e retorna a conexão com o banco de dados."""
    try:
        return psycopg2.connect(**st.secrets["database"])
    except psycopg2.OperationalError as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}. Verifique suas credenciais no secrets.toml.")
        st.stop()

conn = init_connection()

def salvar_historico(nome, profissao, localizacao, titulo, slogan, nivel_concorrencia, alerta):
    """Salva os dados da consulta no banco de dados PostgreSQL."""
    sql = """INSERT INTO consultas (nome_usuario, tipo_negocio_pesquisado, localizacao_pesquisada, nivel_concorrencia_ia, titulo_gerado_ia, slogan_gerado_ia, alerta_oportunidade_ia) VALUES (%s, %s, %s, %s, %s, %s, %s);"""
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (nome, profissao, localizacao, nivel_concorrencia, titulo, slogan, alerta))
            conn.commit()
    except psycopg2.Error as e:
        st.error(f"Erro ao salvar no banco de dados: {e}")
        conn.rollback()

def carregar_logo_base64(caminho):
    try:
        with open(caminho, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        st.warning(f"Arquivo de logo não encontrado em: {caminho}")
        return ""

def limpar_texto_pdf(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = "".join(c for c in texto if unicodedata.category(c) != "So")
    texto = re.sub(r'[^\w\s.,!?-]', '', texto)
    return texto

# --- FUNÇÕES DE API (GOOGLE E OPENAI) ---
def buscar_concorrentes(profissao, localizacao):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": f"{profissao} em {localizacao}", "key": API_KEY_GOOGLE}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get("results", [])
    return []

def buscar_detalhes_lugar(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {"place_id": place_id, "fields": "name,formatted_address,review,formatted_phone_number,website,opening_hours", "key": API_KEY_GOOGLE}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get("result", {})
    return {}

def analisar_sentimentos_por_topico_ia(comentarios):
    prompt = f"""Analise os seguintes comentários de clientes. Para cada um dos tópicos abaixo, atribua uma nota de sentimento de 0 (muito negativo) a 10 (muito positivo), com base na opinião geral. Se um tópico não for mencionado, atribua a nota 5 (neutro). Tópicos: Atendimento, Preço, Qualidade, Ambiente, Tempo de Espera. Responda estritamente no formato JSON: {{"Atendimento": 8, "Preço": 6, "Qualidade": 9, "Ambiente": 7, "Tempo de Espera": 4}}"""
    try:
        resposta = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], temperature=0.2)
        dados = json.loads(resposta.choices[0].message.content)
        topicos_base = {"Atendimento": 5, "Preço": 5, "Qualidade": 5, "Ambiente": 5, "Tempo de Espera": 5}; topicos_base.update(dados)
        return topicos_base
    except (json.JSONDecodeError, KeyError, IndexError):
        return {"Atendimento": 0, "Preço": 0, "Qualidade": 0, "Ambiente": 0, "Tempo de Espera": 0}

def gerar_dossie_concorrente_ia(nome_concorrente, comentarios, horarios):
    prompt = f"""Você é um estrategista de negócios sênior. Baseado nos dados do concorrente '{nome_concorrente}', que possui os seguintes horários de funcionamento: {horarios} e os seguintes comentários de clientes: "{' '.join(comentarios)}", crie um dossiê estratégico. Responda estritamente no seguinte formato JSON: {{"arquétipo": "Um arquétipo curto e impactante (Ex: 'O Padrão Confiável', 'O Barato com Surpresas').", "ponto_forte": "A principal força do concorrente, em uma frase.", "fraqueza_exploravel": "A principal fraqueza que pode ser explorada por um novo negócio, em uma frase.", "resumo_estrategico": "Um parágrafo conciso resumindo a posição estratégica deste concorrente no mercado."}}"""
    try:
        resposta = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], temperature=0.7)
        return json.loads(resposta.choices[0].message.content)
    except (json.JSONDecodeError, KeyError, IndexError):
        return {"arquétipo": "Não foi possível analisar", "ponto_forte": "N/A", "fraqueza_exploravel": "N/A", "resumo_estrategico": "Não foi possível gerar o resumo estratégico."}

def enriquecer_com_ia(sentimentos_dict):
    prompt = f"""Baseado no seguinte diagnóstico de sentimentos (0-10) de um mercado local: {sentimentos_dict}, gere os seguintes insights: Responda estritamente no formato JSON: {{"titulo": "Um título criativo para o relatório.", "slogan": "Um slogan inspirador.", "nivel_concorrencia": "Baixo, Médio ou Alto", "sugestoes_estrategicas": ["Sugestão estratégica 1 baseada no ponto mais fraco.", "Sugestão 2 baseada no ponto mais forte."], "alerta_nicho": "Se houver um tópico com nota muito baixa (menor que 4), escreva um alerta sobre essa oportunidade. Senão, string vazia."}}"""
    try:
        resposta = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], temperature=0.7)
        dados_ia = json.loads(resposta.choices[0].message.content)
        return (dados_ia.get("titulo", "Análise Estratégica"), dados_ia.get("slogan", "Destaque-se."), dados_ia.get("nivel_concorrencia", "N/D"), dados_ia.get("sugestoes_estrategicas", []), dados_ia.get("alerta_nicho", ""))
    except (json.JSONDecodeError, KeyError, IndexError):
        return "Análise Indisponível", "Slogan Indisponível", "Nível Indisponível", [], ""

# --- FUNÇÕES DE GERAÇÃO DE ARQUIVOS ---
def gerar_pdf(html):
    pdf_bytes = BytesIO()
    pisa_status = pisa.CreatePDF(html.encode('utf-8'), dest=pdf_bytes, encoding='utf-8')
    if pisa_status.err:
        html_limpo = limpar_texto_pdf(html); pdf_bytes = BytesIO()
        pisa.CreatePDF(html_limpo.encode('utf-8'), dest=pdf_bytes, encoding='utf-8')
    return pdf_bytes.getvalue()

def gerar_grafico_radar_base64(sentimentos_dict):
    labels = list(sentimentos_dict.keys())
    stats_limpos = []
    for valor in sentimentos_dict.values():
        if isinstance(valor, (int, float)):
            stats_limpos.append(valor)
        elif isinstance(valor, dict):
            nota_extraida = valor.get('nota', valor.get('score', 5))
            stats_limpos.append(nota_extraida if isinstance(nota_extraida, (int, float)) else 5)
        else:
            stats_limpos.append(5)
    stats = stats_limpos
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist(); stats += stats[:1]; angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='#007bff', alpha=0.25); ax.plot(angles, stats, color='#007bff', linewidth=2)
    ax.set_ylim(0, 10); ax.set_yticklabels([]); ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=12); ax.set_title("Diagnóstico de Sentimentos por Tópico", fontsize=16, y=1.1)
    buf = BytesIO(); plt.savefig(buf, format="png", bbox_inches='tight'); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def gerar_grafico_concorrentes_base64(concorrentes):
    if not concorrentes: return ""
    notas=[float(c.get('nota',0)) for c in concorrentes]; avaliacoes=[int(c.get('total_avaliacoes',0)) for c in concorrentes]; nomes=[c.get('nome','') for c in concorrentes]
    if not any(notas) and not any(avaliacoes): return ""
    fig, ax = plt.subplots(figsize=(8, 6)); ax.scatter(notas, avaliacoes, s=100, alpha=0.7, edgecolors="k", c="#4CAF50")
    for i, nome in enumerate(nomes): ax.text(notas[i], avaliacoes[i] + (max(avaliacoes) * 0.02), nome[:15], fontsize=9, ha='center')
    media_nota=sum(notas)/len(notas) if notas else 0; media_avaliacoes=sum(avaliacoes)/len(avaliacoes) if avaliacoes else 0
    ax.axvline(media_nota, color='grey', linestyle='--', linewidth=1); ax.axhline(media_avaliacoes, color='grey', linestyle='--', linewidth=1)
    ax.set_title('Análise de Concorrentes: Qualidade vs. Popularidade', fontsize=14); ax.set_xlabel('Nota Média (Qualidade)', fontsize=12); ax.set_ylabel('Número de Avaliações (Popularidade)', fontsize=12)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    if notas: ax.set_xlim(min(notas)-0.5, max(notas)+0.5)
    if avaliacoes: ax.set_ylim(0, max(avaliacoes)*1.1)
    buf = BytesIO(); plt.savefig(buf, format="png", bbox_inches='tight'); plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def gerar_html_relatorio(**kwargs):
    css = """<style> body { font-family: Arial, sans-serif; } .center { text-align: center; } .report-header { padding-bottom: 20px; border-bottom: 2px solid #eee; } .section { margin-top: 35px; page-break-inside: avoid; } h3 { border-bottom: 1px solid #eee; padding-bottom: 5px;} .slogan { font-style: italic; } .alert { border: 1px solid #f44336; background-color: #ffe6e6; padding: 15px; margin-top: 20px; } table { border-collapse: collapse; width: 100%; font-size: 12px; } th, td { border: 1px solid #ccc; padding: 8px; } th { background-color: #f2f2f2; } .dossier-card { border: 1px solid #ddd; padding: 15px; margin-top: 20px; page-break-inside: avoid; border-radius: 8px; background-color: #f9f9f9; } .review { border-left: 3px solid #ccc; padding-left: 10px; margin-top: 10px; font-style: italic; } </style>"""
    dossie_html = ""
    for c in kwargs.get("concorrentes", []):
        dossie_ia = c.get('dossie_ia', {})
        horarios_html = "<ul>" + "".join(f"<li>{h}</li>" for h in c.get('horarios', ['Não informado'])) + "</ul>"
        review_pos = f"<div class='review'><strong>👍 Positiva:</strong> {c.get('review_positivo_exemplo', 'Nenhuma avaliação positiva encontrada.')}</div>"
        review_neg = f"<div class='review'><strong>👎 Negativa:</strong> {c.get('review_negativo_exemplo', 'Nenhuma avaliação negativa encontrada.')}</div>"
        dossie_html += f"""<div class='dossier-card'><h4>{c.get('nome', 'Concorrente')}</h4><p><strong>Endereço:</strong> {c.get('endereco', 'Não informado')}</p><p><strong>Arquétipo Estratégico:</strong> {dossie_ia.get('arquétipo', 'N/A')}</p><p>{dossie_ia.get('resumo_estrategico', '')}</p><strong>Horário de Funcionamento:</strong>{horarios_html}<strong>Amostra de Avaliações de Clientes:</strong>{review_pos}{review_neg}</div>"""
        
    body = f"""<html><head><meta charset='utf-8'>{css}</head><body>
        <div class='report-header center'><img src='data:image/png;base64,{kwargs.get("base64_logo")}' width='120'><h1>{kwargs.get("titulo")}</h1><p class='slogan'>"{kwargs.get("slogan")}"</p><p>Análise de Concorrência para <strong>{kwargs.get("tipo_negocio")}</strong></p><p><small>Gerado para: {kwargs.get("nome_usuario")} em {kwargs.get("data_hoje")}</small></p></div>
        <div class='section center'><h3>Diagnóstico Geral do Mercado</h3><img src='data:image/png;base64,{kwargs.get("grafico_radar_b64")}' width='500'></div>
        <div class='section'><h3>Sugestões Estratégicas</h3><ul>{''.join(f"<li>{s}</li>" for s in kwargs.get("sugestoes_estrategicas", []))}</ul></div>
        {f"<div class='section alert'><h3>🚨 Alerta de Oportunidade</h3><p>{kwargs.get('alerta_nicho')}</p></div>" if kwargs.get('alerta_nicho') else ""}
        <div class='section center'><h3>Posicionamento dos Concorrentes</h3><img src='data:image/png;base64,{kwargs.get("grafico_concorrentes_b64")}' width='600'></div>
        <div class='section'><h3>Visão Geral dos Concorrentes</h3><table><tr><th>Nome</th><th>Nota</th><th>Total Aval.</th><th>Preço</th><th>Site</th></tr>{''.join(f"<tr><td>{c.get('nome')}</td><td>{c.get('nota')}</td><td>{c.get('total_avaliacoes')}</td><td>{c.get('price_level', '-')}</td><td><a href='{c.get('site', '#')}'>Visitar</a></td></tr>" for c in kwargs.get("concorrentes", []))}</table></div>
        <div class='section' style='page-break-before: always;'><h3>Apêndice: Dossiê Detalhado dos Concorrentes</h3>{dossie_html}</div>
        </body></html>"""
    return body

# --- INTERFACE PRINCIPAL DO STREAMLIT ---
base64_logo = carregar_logo_base64("logo_radar_local.png")
st.markdown(f"""<div style='text-align: center;'><img src='data:image/png;base64,{base64_logo}' width='120'><h1 style='font-size: 2.5em;'>Radar Local</h1><p style='font-size: 1.2em; color: #555;'>Inteligência de Mercado para Autônomos e Pequenos Negócios</p></div>""", unsafe_allow_html=True)
st.markdown("---")

with st.form("formulario_principal"):
    st.subheader("🕵️‍♀️ Comece sua Análise Premium")
    col1, col2, col3 = st.columns(3)
    with col1:
        profissao = st.text_input("Sua profissão ou tipo de negócio?", placeholder="Ex: Barbearia")
    with col2:
        localizacao = st.text_input("Sua cidade ou bairro?", placeholder="Ex: Vila Prudente, SP")
    with col3:
        nome_usuario = st.text_input("Seu nome (para o relatório)", placeholder="Ex: João Silva")
    enviar = st.form_submit_button("🔍 Gerar Análise Completa")

if enviar:
    if not all([profissao, localizacao, nome_usuario]):
        st.warning("⚠️ Por favor, preencha todos os campos.")
    else:
        with st.spinner("Analisando concorrentes e gerando dossiês estratégicos... Isso pode levar um minuto."):
            resultados_google = buscar_concorrentes(profissao, localizacao)
            if not resultados_google: st.info("Nenhum concorrente encontrado. Tente termos diferentes."); st.stop()
            
            concorrentes_formatados = []
            comentarios_total = []
            for lugar in resultados_google[:5]:
                if not lugar.get("place_id"): continue
                detalhes = buscar_detalhes_lugar(lugar.get("place_id"))
                reviews = detalhes.get("reviews", [])
                comentarios_individuais = [r.get("text", "") for r in reviews if r.get("text")]
                dossie_ia = gerar_dossie_concorrente_ia(lugar.get('name'), comentarios_individuais, detalhes.get('opening_hours', {}).get('weekday_text', []))
                review_pos = next((r['text'] for r in reviews if r.get('rating', 0) >= 4), None)
                review_neg = next((r['text'] for r in reviews if r.get('rating', 0) <= 2), None)
                
                concorrentes_formatados.append({
                    "nome": lugar.get("name"), "endereco": detalhes.get('formatted_address'), "nota": lugar.get("rating"), "total_avaliacoes": lugar.get("user_ratings_total"), 
                    "price_level": lugar.get("price_level"), "site": detalhes.get("website", ""), "horarios": detalhes.get('opening_hours', {}).get('weekday_text', []),
                    "dossie_ia": dossie_ia, "review_positivo_exemplo": review_pos, "review_negativo_exemplo": review_neg
                })
                comentarios_total.extend(comentarios_individuais)

            sentimentos_dict = analisar_sentimentos_por_topico_ia("\n".join(comentarios_total[:20]))
            titulo, slogan, nivel, sugestoes_estrategicas, alerta = enriquecer_com_ia(sentimentos_dict)
            
            salvar_historico(nome_usuario, profissao, localizacao, titulo, slogan, nivel, alerta)

            grafico_radar_b64 = gerar_grafico_radar_base64(sentimentos_dict)
            grafico_concorrentes_b64 = gerar_grafico_concorrentes_base64(concorrentes_formatados)

            dados_html = {
                "base64_logo": base64_logo, "titulo": titulo, "slogan": slogan, "tipo_negocio": profissao, "nome_usuario": nome_usuario, 
                "data_hoje": datetime.now().strftime("%d/%m/%Y %H:%M"), "sugestoes_estrategicas": sugestoes_estrategicas, "alerta_nicho": alerta,
                "grafico_radar_b64": grafico_radar_b64, "grafico_concorrentes_b64": grafico_concorrentes_b64, "concorrentes": concorrentes_formatados
            }
            html_relatorio = gerar_html_relatorio(**dados_html)
            
            pdf_bytes = gerar_pdf(html_relatorio)
            st.success("✅ Análise Premium concluída com sucesso!")
            st.markdown("---"); st.subheader(f"📄 Relatório Estratégico para {profissao} em {localizacao}")
            st.components.v1.html(html_relatorio, height=600, scrolling=True)

            if pdf_bytes:
                st.download_button("⬇️ Baixar Relatório Premium em PDF", pdf_bytes, f"relatorio_premium_{profissao.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.pdf", "application/pdf")

# --- PAINEL DE ADMINISTRADOR ---
st.markdown("---")
def check_password():
    with st.sidebar.form("password_form"):
        st.markdown("### Acesso Restrito")
        password = st.text_input("Senha de Administrador", type="password")
        submitted = st.form_submit_button("Acessar")
        if submitted:
            if password == st.secrets["admin"]["password"]:
                st.session_state["password_correct"] = True; st.rerun()
            else:
                st.error("Senha incorreta.")
    return False

if st.session_state.get("password_correct", False):
    st.sidebar.success("Acesso de administrador concedido!")
    st.subheader("📊 Painel de Administrador")
    path_historico = Path("historico_consultas.csv")
    if path_historico.exists():
        with st.expander("Ver Histórico de Consultas", expanded=True):
            df_historico = pd.read_csv(path_historico); st.dataframe(df_historico)
            st.markdown("#### Análise Rápida"); col1, col2 = st.columns(2)
            with col1: st.write("**Negócios Mais Pesquisados:**"); st.bar_chart(df_historico['tipo_negocio_pesquisado'].value_counts())
            with col2: st.write("**Localizações Mais Pesquisadas:**"); st.bar_chart(df_historico['localizacao_pesquisada'].value_counts())
    else:
        st.info("O histórico de consultas ainda não foi criado.")
else:
    check_password()