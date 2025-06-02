import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from unidecode import unidecode

API_URL = "https://techchallengeapi.onrender.com/api/v1"
LOGIN_URL = f"{API_URL}/users/login"
SIGNUP_URL = f"{API_URL}/users/signup"

ENDPOINTS = {
    "Importação": "importacoes",
    "Exportação": "exportacoes",
    "Produção": "producoes",
    "Processamento": "processamentos",
    "Comercialização": "comercializacoes"
}

def wake_up_api():
    try:
        r = requests.get(f"{API_URL}", timeout=5)
        if r.status_code == 200:
            mensagem = r.json().get("mensagem", "API acordada!")
            st.info(mensagem)
        else:
            st.warning("Aguardando API...")
    except:
        st.warning("Iniciando a API... aguarde alguns segundos.")

st.set_page_config(page_title="Viticultura Dashboard", layout="wide")

if "token" not in st.session_state:
    st.session_state.token = None

wake_up_api()

def autenticar_usuario(email, senha):
    payload = {"username": email, "password": senha}
    try:
        response = requests.post(LOGIN_URL, data=payload)
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        st.error("Falha no login: " + str(e))
        return None

def cadastrar_usuario(name, surname, email, password):
    payload = {"name": name, "surname": surname, "email": email, "password": password}
    try:
        response = requests.post(SIGNUP_URL, json=payload)
        if response.status_code == 400:
            msg = response.json().get("detail", "")
            if "already registered" in msg.lower():
                st.error("Este e-mail já está cadastrado. Tente fazer login.")
                return
        response.raise_for_status()
        st.success("Usuário criado com sucesso! Entrando...")
        token = autenticar_usuario(email, password)
        if token:
            st.session_state.token = token
            st.rerun()
    except Exception as e:
        st.error(f"Erro ao cadastrar: {e}")

def carregar_dados(endpoint):
    url = f"{API_URL}/{endpoint}/"
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return pd.DataFrame(response.json())
    except Exception as e:
        st.error(f"Erro ao carregar dados de {endpoint}: {e}")
        return pd.DataFrame()

def detectar_coluna_produto(df):
    for col in ["produto", "produto_nome", "produto_tipo"]:
        if col in df.columns:
            return col
    return None

def aplicar_filtros(df, produto_col, busca, anos, produtos):
    if produtos and produto_col:
        df = df[df[produto_col].isin(produtos)]
    if busca and produto_col:
        busca_proc = unidecode(busca.lower())
        df = df[
            df[produto_col].apply(lambda x: busca_proc in unidecode(str(x).lower())) |
            df["pais"].apply(lambda x: busca_proc in unidecode(str(x).lower())) if "pais" in df.columns else False
        ]
    return df

if not st.session_state.token:
    st.markdown("<h2 style='text-align: center;'>🔐 Acesso Restrito</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Faça login ou crie uma nova conta para continuar</p>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Entrar", "Cadastrar"])

    with tab1:
        st.markdown("### Login")
        with st.form("login_form"):
            email = st.text_input("E-mail", placeholder="Digite seu e-mail")
            senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            submitted = st.form_submit_button("Entrar")
            if submitted:
                token = autenticar_usuario(email, senha)
                if token:
                    st.session_state.token = token
                    st.success("Login realizado com sucesso!")
                    st.rerun()

    with tab2:
        st.markdown("### Criar Conta")
        with st.form("signup_form"):
            name = st.text_input("Nome", placeholder="Seu nome")
            surname = st.text_input("Sobrenome", placeholder="Seu sobrenome")
            email = st.text_input("E-mail", placeholder="Digite um e-mail válido")
            password = st.text_input("Senha", type="password", placeholder="Crie uma senha")
            if st.form_submit_button("Cadastrar"):
                cadastrar_usuario(name, surname, email, password)

else:
    st.sidebar.success("Autenticado")
    
    st.sidebar.link_button("API DOCS", url="https://techchallengeapi.onrender.com/docs")
    
    menu = st.sidebar.radio("Selecionar categoria", list(ENDPOINTS.keys()))
    endpoint = ENDPOINTS[menu]

    st.title(f"Dashboard: {menu}")
    df = carregar_dados(endpoint)

    if not df.empty:
        produto_col = detectar_coluna_produto(df)
        if produto_col:
            df = df[~df[produto_col].str.fullmatch(r"[A-ZÇÃÂÊÁÉÍÓÚÜÑ ]+")]

        st.sidebar.markdown("### Filtros")
        if "ano" in df.columns:
            anos_disponiveis = sorted(df["ano"].dropna().unique())
            ano_min, ano_max = int(min(anos_disponiveis)), int(max(anos_disponiveis))
            anos = st.sidebar.slider("Ano (intervalo)", min_value=ano_min, max_value=ano_max,
                                     value=(ano_min, ano_max))
            df = df[df["ano"].between(anos[0], anos[1])]

        produtos = st.sidebar.multiselect("Produto(s)", sorted(df[produto_col].dropna().unique())) if produto_col else []
        busca = st.sidebar.text_input("Buscar produto ou país (ignora acento)")

        df_filtrado = aplicar_filtros(df, produto_col, busca, anos, produtos)

        col = st.radio("Visualizar por:", [c for c in ["quantidade", "valor"] if c in df.columns], horizontal=True)

        aba_tabela, aba_grafico_barra, aba_linha, aba_top, aba_comparacao = st.tabs([
            "Tabela", "Barra", "Linha", "Top 5", "Comparação"
        ])

        if st.sidebar.button("Logout", type="primary"):
            st.session_state.token = None
            st.rerun()       

        with aba_tabela:
            st.subheader("Tabela de Dados")
            st.dataframe(df_filtrado)

            col1, col2, col3 = st.columns(3)

            with col1:
                st.download_button("📥 CSV", data=df_filtrado.to_csv(index=False), file_name="dados.csv", mime="text/csv")
            with col2:
                import io
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Dados")
                st.download_button("📥 Excel", data=excel_buffer.getvalue(), file_name="dados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with col3:
                st.download_button("📥 JSON", data=df_filtrado.to_json(orient="records", force_ascii=False), file_name="dados.json", mime="application/json")

        if not df_filtrado.empty:
            with aba_grafico_barra:
                grafico = df_filtrado.groupby("ano")[col].sum().reset_index()
                fig_bar = px.bar(grafico, x="ano", y=col, title=f"{col.title()} por Ano", text_auto=True)
                st.plotly_chart(fig_bar, use_container_width=True)

            with aba_linha:
                fig_linha = px.line(grafico, x="ano", y=col, markers=True, title=f"Evolução de {col}")
                st.plotly_chart(fig_linha, use_container_width=True)

            if produto_col:
                with aba_top:
                    top = df_filtrado.groupby(produto_col)[col].sum().nlargest(5).reset_index()
                    fig_top = px.bar(top, x=produto_col, y=col, title=f"Top 5 {produto_col}", text_auto=True)
                    st.plotly_chart(fig_top, use_container_width=True)

        else:
            st.warning("Nenhum dado encontrado com os filtros aplicados.")
    else:
        st.warning(f"Nenhum dado disponível para {menu}.")

    with aba_comparacao:
            st.subheader("Comparação entre Períodos")

            anos_disponiveis = sorted(df_filtrado["ano"].dropna().unique())
            if len(anos_disponiveis) < 2:
                st.warning("São necessários pelo menos dois anos distintos para comparar.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    periodo1 = st.selectbox("Período 1", anos_disponiveis, index=0)
                with col2:
                    periodo2 = st.selectbox("Período 2", anos_disponiveis, index=1 if len(anos_disponiveis) > 1 else 0)

                if periodo1 == periodo2:
                    st.warning("Selecione dois anos diferentes.")
                else:
                    df1 = df_filtrado[df_filtrado["ano"] == periodo1]
                    df2 = df_filtrado[df_filtrado["ano"] == periodo2]

                    col_comp = "quantidade" if "quantidade" in df_filtrado.columns else "valor"
                    comp_df = pd.merge(
                        df1.groupby(produto_col)[col_comp].sum().reset_index().rename(columns={col_comp: f"{periodo1}"}),
                        df2.groupby(produto_col)[col_comp].sum().reset_index().rename(columns={col_comp: f"{periodo2}"}),
                        on=produto_col,
                        how="inner"
                    )

                    comp_df = comp_df.sort_values(by=f"{periodo2}", ascending=False).head(10)
                    fig_comp = px.bar(
                        comp_df.melt(id_vars=produto_col, var_name="Ano", value_name=col_comp),
                        x=produto_col, y=col_comp, color="Ano", barmode="group",
                        title=f"Top 10 Produtos - {periodo1} vs {periodo2}"
                    )
                    st.plotly_chart(fig_comp, use_container_width=True)
