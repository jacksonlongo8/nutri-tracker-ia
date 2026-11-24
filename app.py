import base64
import json
import os
from io import BytesIO
import streamlit as st
from PIL import Image
from groq import Groq

st.set_page_config(
    page_title="Nutri IA",
    page_icon="🥗",
    layout="centered",
)

# Inicializa estados da sessão
if "refeicoes" not in st.session_state:
    st.session_state.refeicoes = []

if "metas" not in st.session_state:
    st.session_state.metas = {
        "calorias": 2400,
        "proteina": 180,
        "carboidrato": 240,
        "gordura": 70,
    }

if "chat_nutri" not in st.session_state:
    st.session_state.chat_nutri = [
        {
            "role": "assistant",
            "content": "Oi! Já estou acompanhando suas metas e o que você comeu hoje. Pode me perguntar substituições de alimentos, ideias para a próxima refeição ou como bater sua proteína!"
        }
    ]

# Leitura segura da chave Groq
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        api_key = None


def imagem_para_base64(imagem: Image.Image) -> str:
    img_rgb = imagem.convert("RGB")
    img_rgb.thumbnail((1024, 1024))
    buffer = BytesIO()
    img_rgb.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


st.title("🥗 Nutri IA")
st.caption("Contagem rápida de macros + Chat de substituições")

if not api_key:
    api_key = st.text_input("Cole sua GROQ_API_KEY (gsk_...):", type="password")

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

# Cálculos do dia
metas = st.session_state.metas
total_cal = sum(item["calorias"] for item in st.session_state.refeicoes)
total_prot = sum(item["proteina"] for item in st.session_state.refeicoes)
total_carb = sum(item["carboidrato"] for item in st.session_state.refeicoes)
total_gord = sum(item["gordura"] for item in st.session_state.refeicoes)

rest_cal = max(metas["calorias"] - total_cal, 0)
rest_prot = max(metas["proteina"] - total_prot, 0)
rest_carb = max(metas["carboidrato"] - total_carb, 0)
rest_gord = max(metas["gordura"] - total_gord, 0)

# Painel de progresso sempre visível no topo
st.markdown(f"**Calorias:** {total_cal:.0f} / {metas['calorias']} kcal *(Faltam {rest_cal:.0f} kcal)*")
st.progress(min(total_cal / max(metas["calorias"], 1), 1.0))

col1, col2, col3 = st.columns(3)
col1.metric("Proteína", f"{total_prot:.0f}g", f"Falta: {rest_prot:.0f}g")
col2.metric("Carbo", f"{total_carb:.0f}g", f"Falta: {rest_carb:.0f}g")
col3.metric("Gordura", f"{total_gord:.0f}g", f"Falta: {rest_gord:.0f}g")

st.divider()

# Abas principais
aba_diario, aba_chat = st.tabs(["🍽️ Registrar Refeição", "💬 Chat Nutri & Trocas"])

with aba_diario:
    descricao_texto = st.text_area(
        "O que você comeu? (opcional se enviar foto)",
        placeholder="Ex: 150g de frango grelhado, 200g de arroz branco e 1 colher de azeite",
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
            st.error("Informe sua GROQ_API_KEY antes de analisar.")
        elif not descricao_texto.strip() and imagem_pil is None:
            st.warning("Escreva o que você comeu ou envie uma foto do prato.")
        else:
            with st.spinner("Calculando macros..."):
                try:
                    client = Groq(api_key=api_key)

                    prompt_sistema = (
                        "Você é um assistente de contagem nutricional focado em alimentos brasileiros (Tabela TACO). "
                        "Estime calorias, proteína, carboidrato e gordura em gramas de forma realista. "
                        "Responda APENAS com um JSON válido no formato exato: "
                        '{"nome_refeicao": "resumo curto", "calorias": 0, "proteina": 0, "carboidrato": 0, "gordura": 0, "observacao": "dica curta"}'
                    )

                    if imagem_pil is not None:
                        img_b64 = imagem_para_base64(imagem_pil)
                        texto_usuario = descricao_texto.strip() or "Analise os alimentos e porções desta foto."
                        mensagens = [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"{prompt_sistema}\n\nRefeição: {texto_usuario}"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                                ],
                            }
                        ]
                        modelo = "meta-llama/llama-4-scout-17b-16e-instruct"
                    else:
                        mensagens = [
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": f"Refeição: {descricao_texto.strip()}"},
                        ]
                        modelo = "llama-3.3-70b-versatile"

                    completion = client.chat.completions.create(
                        model=modelo,
                        messages=mensagens,
                        response_format={"type": "json_object"},
                        temperature=0.2,
                    )

                    dados = json.loads(completion.choices[0].message.content)
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

with aba_chat:
    st.caption("Ex: 'Não tenho frango, troco 150g por quanto de ovo?' ou 'O que comer no jantar com o que falta?'")

    for msg in st.session_state.chat_nutri:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pergunta = st.chat_input("Pergunte sobre substituições, porções ou refeições...")
    if pergunta:
        if not api_key:
            st.error("Informe sua GROQ_API_KEY no topo da página.")
        else:
            st.session_state.chat_nutri.append({"role": "user", "content": pergunta})
            with st.chat_message("user"):
                st.markdown(pergunta)

            with st.chat_message("assistant"):
                with st.spinner("Pensando..."):
                    try:
                        client = Groq(api_key=api_key)
                        resumo_refeicoes = ", ".join(
                            [f"{r['nome_refeicao']} ({r['calorias']:.0f} kcal, {r['proteina']:.0f}g prot)" for r in st.session_state.refeicoes]
                        ) or "Nenhuma refeição registrada ainda."

                        contexto_nutri = f"""
                        Você é um assistente de nutrição esportiva prático, direto e amigável, focado em alimentos brasileiros (Tabela TACO).
                        Ajude o usuário com substituições equivalentes em gramas, ideias de refeições e ajustes de dieta.
                        Seja objetivo, use listas curtas e informe sempre as gramas exatas nas substituições.

                        Dados atuais do usuário hoje:
                        - Meta diária: {metas['calorias']} kcal | {metas['proteina']}g Proteína | {metas['carboidrato']}g Carbo | {metas['gordura']}g Gordura
                        - Já consumido hoje: {total_cal:.0f} kcal | {total_prot:.0f}g Proteína | {total_carb:.0f}g Carbo | {total_gord:.0f}g Gordura
                        - Ainda falta bater hoje: {rest_cal:.0f} kcal | {rest_prot:.0f}g Proteína | {rest_carb:.0f}g Carbo | {rest_gord:.0f}g Gordura
                        - Refeições feitas hoje: {resumo_refeicoes}
                        """

                        historico_envio = [{"role": "system", "content": contexto_nutri}] + st.session_state.chat_nutri[-8:]

                        resposta_chat = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=historico_envio,
                            temperature=0.4,
                            max_tokens=700,
                        )
                        texto_resposta = resposta_chat.choices[0].message.content
                        st.markdown(texto_resposta)
                        st.session_state.chat_nutri.append({"role": "assistant", "content": texto_resposta})
                    except Exception as e:
                        st.error(f"Erro no chat: {e}")
