import streamlit as st
import requests
from openai import OpenAI
import pdfkit
from datetime import datetime
import base64
import pandas as pd

# Configuração das chaves e do wkhtmltopdf
AAPI_KEY_GOOGLE = st.secrets["google"]["api_key"]
client = OpenAI(api_key=st.secrets["openai"]["api_key"])
wkhtmltopdf_path = "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
pdf_config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

# Carrega o logo como base64 para Streamlit e PDF
def carregar_logo_base64(caminho):
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

base64_logo = carregar_logo_base64("logo_radar_local.png")

# Interface inicial
st.markdown(f"""
    <div style='text-align: center;'>
        <img src='data:image/png;base64,{base64_logo}' width='120'>
        <h1 style='font-size: 2.5em;'>Inteligência de Mercado para Autônomos</h1>
        <p style='max-width: 700px; margin: auto; font-size: 1.1em; line-height: 1.6;'>
            Descubra seus concorrentes locais, analise as avaliações reais do Google e receba sugestões de diferenciação com inteligência artificial. Ideal para autônomos e pequenos negócios.
        </p>
    </div>
""", unsafe_allow_html=True)

# Funções principais
def buscar_concorrentes(profissao, localizacao):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": f"{profissao} em {localizacao}", "key": API_KEY_GOOGLE}
    response = requests.get(url, params=params)
    return response.json().get("results", []) if response.status_code == 200 else []

def buscar_comentarios(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {"place_id": place_id, "fields": "review", "key": API_KEY_GOOGLE}
    response = requests.get(url, params=params)
    reviews = response.json().get("result", {}).get("reviews", [])
    return [r.get("text", "") for r in reviews if r.get("text")]

def gerar_resumo_openai(comentarios):
    prompt = f"""
Você é um consultor de marketing para autônomos. Analise os comentários abaixo:
{comentarios}
1. Quais elogios são mais frequentes?
2. Quais reclamações são mais comuns?
3. Dê 3 sugestões práticas para um novo profissional se destacar.
"""
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=600
    )
    return resposta.choices[0].message.content

def enriquecer_com_ia(comentarios, nota_media, faixa_preco):
    prompt = f"""
Você é um consultor de marketing.
Baseando-se na média de avaliação {nota_media}, faixa de preço {faixa_preco}, e nestes comentários:
{comentarios}
Responda:
1. Um título impactante para o relatório.
2. Um slogan com tom inspirador para pequenos negócios.
3. Classifique o nível de concorrência como: Baixo, Médio ou Alto.
4. Liste 3 sugestões estratégicas para se diferenciar.
5. Há um nicho promissor com nota baixa e concorrência fraca? Se sim, escreva um alerta.
"""
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=800
    )
    texto = resposta.choices[0].message.content

    # Simples extração de informações com split (pode ajustar se quiser algo mais robusto)
    partes = texto.split("\n")
    titulo = partes[0].replace("1. ", "").strip()
    slogan = partes[1].replace("2. ", "").strip()
    nivel = partes[2].replace("3. ", "").strip()
    sugestoes = [p.replace("-", "").strip() for p in partes[3:6] if p.strip()]
    alerta = partes[6].replace("5. ", "").strip() if len(partes) > 6 else ""

    return titulo, slogan, nivel, sugestoes, alerta

def gerar_html(profissao, localizacao, concorrentes, resumo, titulo, slogan, nivel_concorrencia, sugestoes, alerta_nicho, base64_logo):
    logo_html = f"<img src='data:image/png;base64,{base64_logo}' width='120' style='display:block; margin:auto;'>"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            h1 {{ color: #004080; text-align: center; }}
            .box {{ border: 1px solid #ddd; margin-bottom: 10px; padding: 10px; }}
            .badge {{ background-color: #eee; padding: 5px 10px; border-radius: 5px; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        {logo_html}
        <h1>{titulo}</h1>
        <p style='text-align:center; font-style: italic;'>{slogan}</p>
        <p><strong>Profissão:</strong> {profissao}</p>
        <p><strong>Localização:</strong> {localizacao}</p>
        <p><strong>Nível de Concorrência:</strong> <span class='badge'>{nivel_concorrencia}</span></p>
        <hr>
    """

    for c in concorrentes:
        html += f"""
        <div class='box'>
            <h3>Concorrente: {c['nome']}</h3>
            <p><strong>Nota:</strong> {c['nota']}</p>
            <p><strong>Endereço:</strong> {c['endereco']}</p>
            <p><strong>Comentários:</strong></p>
            <ul>
        """
        for com in c['comentarios']:
            html += f"<li>{com}</li>"
        html += "</ul></div>"

    html += f"""
        <h2>Análise Inteligente</h2>
        <p>{resumo}</p>
        <h3>🎯 Sugestões Estratégicas</h3>
        <ul>
    """
    for sugestao in sugestoes:
        html += f"<li>{sugestao}</li>"
    html += "</ul>"

    if alerta_nicho:
        html += f"<div style='margin-top:20px; padding:10px; border-left: 5px solid green; background-color: #f0fff0;'><strong>🚀 Nicho Promissor:</strong> {alerta_nicho}</div>"

    html += """
    </body>
    </html>
    """
    return html

# Interface principal
with st.form("formulario"):
    profissao = st.text_input("Qual é a sua profissão?", placeholder="Ex: Barbearia")
    localizacao = st.text_input("Qual é sua cidade ou bairro?", placeholder="Ex: Vila Prudente")
    enviar = st.form_submit_button("🔍 Buscar concorrência")

if enviar and profissao and localizacao:
    st.success(f"Buscando concorrentes de **{profissao}** em **{localizacao}**...")
    resultados = buscar_concorrentes(profissao, localizacao)

    if resultados:
        comentarios_total = []
        concorrentes_formatados = []

        for lugar in resultados[:3]:
            nome = lugar["name"]
            nota = lugar.get("rating", "Sem avaliação")
            endereco = lugar.get("formatted_address", "Endereço não disponível")
            place_id = lugar.get("place_id")
            comentarios = buscar_comentarios(place_id)

            concorrentes_formatados.append({
                "nome": nome,
                "nota": nota,
                "endereco": endereco,
                "comentarios": comentarios[:2]
            })

            comentarios_total.extend(comentarios)

        resumo = gerar_resumo_openai("\n".join(comentarios_total[:10]))
        st.subheader("📊 Análise inteligente dos comentários")
        st.write(resumo)

        # Métricas simuladas
        nota_media = 4.3
        faixa_preco = 2
        df_metricas = pd.DataFrame({
            "Bairro": [localizacao],
            "Avaliação Média": [nota_media],
            "Faixa de Preço Média": [faixa_preco]
        })
        st.subheader("📋 Tabela de Avaliação e Faixa de Preço")
        st.dataframe(df_metricas)

        titulo, slogan, nivel, sugestoes, alerta = enriquecer_com_ia("\n".join(comentarios_total[:10]), nota_media, faixa_preco)

        # Geração do PDF
        html = gerar_html(profissao, localizacao, concorrentes_formatados, resumo, titulo, slogan, nivel, sugestoes, alerta, base64_logo)
        pdf_bytes = pdfkit.from_string(html, False, configuration=pdf_config)

        st.download_button(
            label="⬇️ Baixar relatório em PDF",
            data=pdf_bytes,
            file_name=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )
    else:
        st.info("Nenhum concorrente encontrado.")
elif enviar:
    st.warning("Preencha todos os campos.")
