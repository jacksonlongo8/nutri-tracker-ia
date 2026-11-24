import json
import os
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Nutri Jackson Longo IA",
    page_icon="🥗",
    layout="centered",
)

# Inicializa estado da sessão
if "refeicoes" not in st.session_state:
    st.session_state.refeicoes = []

if "metas" not in st.session_state:
    st.session_state.metas = {
        "calorias": 2400,
        "proteina": 180,
        "carboidrato": 240,
        "gordura": 70,
    }

# Leitura segura da chave (variável de ambiente ou st.secrets)
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        api_key = None

st.title("🥗 Nutri Tracker IA")
st.caption("Registro de refeições por foto ou texto")

with st.expander("⚙️ Configurar metas diárias"):
    c1, c2 = st.columns(2)
    with c1:
        meta_cal = st.number_input("Calorias (kcal)", min_value=800, max_value=8000, value=st.session_state.metas["calorias"], step=50)
        meta_prot = st.number_input("Proteína (g)", min_value=20, max_value=500, value=st.session_state.metas["proteina"], step=5)
    with c2:
        meta_carb = st.number_input("Carboidrato (g)", min_value=0, max_value=1000, value=st.session_state.metas["carboidrato"], step=10)
        meta_gord = st.number_input("Gordura (g)", min_value=10, max_value=300, value=st.session_state.metas["gordura"], step=5)

    if st.button("Salvar metas", use_container_width=True):
        st.session_state.metas = {
            "calorias": meta_cal,
            "proteina": meta_prot,
            "carboidrato": meta_carb,
            "gordura": meta_gord,
        }
        st.success("Metas atualizadas!")

# Totais consumidos no dia
total_cal = sum(item["calorias"] for item in st.session_state.refeicoes)
total_prot = sum(item["proteina"] for item in st.session_state.refeicoes)
total_carb = sum(item["carboidrato"] for item in st.session_state.refeicoes)
total_gord = sum(item["gordura"] for item in st.session_state.refeicoes)

metas = st.session_state.metas

st.subheader("📊 Resumo do dia")
st.markdown(f"**Calorias:** {total_cal:.0f} / {metas['calorias']} kcal")
st.progress(min(total_cal / max(metas["calorias"], 1), 1.0))

col1, col2, col3 = st.columns(3)
col1.metric("Proteína", f"{total_prot:.0f}g", f"Meta: {metas['proteina']}g")
col2.metric("Carbo", f"{total_carb:.0f}g", f"Meta: {metas['carboidrato']}g")
col3.metric("Gordura", f"{total_gord:.0f}g", f"Meta: {metas['gordura']}g")

st.divider()
st.subheader("➕ Registrar refeição")

if not api_key:
    api_key = st.text_input("Cole sua GEMINI_API_KEY para testar agora:", type="password")

descricao_texto = st.text_area(
    "O que você comeu? (opcional se enviar foto)",
    placeholder="Ex: 150g de frango grelhado, 180g de arroz branco e 1 colher de azeite",
)

aba_foto = st.radio("Enviar imagem do prato:", ["Nenhuma", "Tirar foto / Escolher arquivo"], horizontal=True)
imagem_pil = None

if aba_foto == "Tirar foto / Escolher arquivo":
    arquivo_img = st.file_uploader("Foto da refeição", type=["jpg", "jpeg", "png", "webp"])
    if arquivo_img is not None:
        imagem_pil = Image.open(arquivo_img)
        st.image(imagem_pil, caption="Prévia da refeição", use_container_width=True)

if st.button("Analisar e adicionar refeição", type="primary", use_container_width=True):
    if not api_key:
        st.error("Informe sua GEMINI_API_KEY antes de analisar.")
    elif not descricao_texto.strip() and imagem_pil is None:
        st.warning("Escreva o que você comeu ou envie uma foto do prato.")
    else:
        with st.spinner("Analisando refeição com a IA..."):
            try:
                client = genai.Client(api_key=api_key)

                prompt = """
                Você é um assistente de contagem nutricional focado em alimentos do dia a dia brasileiro.
                Analise a refeição informada (por texto, imagem ou ambos) e estime as porções em gramas
                com base na Tabela TACO e referências nutricionais padrão.
                Seja realista e conservador nas estimativas de óleos, molhos e acompanhamentos.
                Retorne APENAS um JSON válido com esta estrutura exata:
                {
                  "nome_refeicao": "resumo curto da refeição",
                  "calorias": 0,
                  "proteina": 0,
                  "carboidrato": 0,
                  "gordura": 0,
                  "observacao": "observação curta sobre porções ou pontos de atenção"
                }
                """

                contents = [prompt]
                if descricao_texto.strip():
                    contents.append(f"Descrição do usuário: {descricao_texto.strip()}")
                if imagem_pil is not None:
                    contents.append(imagem_pil)

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )

                dados = json.loads(response.text)
                nova_refeicao = {
                    "nome_refeicao": str(dados.get("nome_refeicao", "Refeição")),
                    "calorias": float(dados.get("calorias", 0)),
                    "proteina": float(dados.get("proteina", 0)),
                    "carboidrato": float(dados.get("carboidrato", 0)),
                    "gordura": float(dados.get("gordura", 0)),
                    "observacao": str(dados.get("observacao", "")),
                }
                st.session_state.refeicoes.append(nova_refeicao)
                st.rerun()

            except Exception as e:
                st.error(f"Erro ao processar a refeição: {e}")

st.divider()
st.subheader("📋 Refeições de hoje")

if not st.session_state.refeicoes:
    st.info("Nenhuma refeição registrada ainda.")
else:
    for ref in reversed(st.session_state.refeicoes):
        with st.container(border=True):
            st.markdown(f"**{ref['nome_refeicao']}**")
            st.write(
                f"🔥 **{ref['calorias']:.0f} kcal** | "
                f"🥩 Prot: **{ref['proteina']:.0f}g** | "
                f"🍚 Carb: **{ref['carboidrato']:.0f}g** | "
                f"🥑 Gord: **{ref['gordura']:.0f}g**"
            )
            if ref.get("observacao"):
                st.caption(ref["observacao"])

    if st.button("Limpar refeições do dia", use_container_width=True):
        st.session_state.refeicoes = []
        st.rerun()