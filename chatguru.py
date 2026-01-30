import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
from datetime import datetime

# ==========================================
# 1. CONFIGURAÇÕES E CARREGAMENTO
# ==========================================
FILE_SUPORTE = 'suporte.csv'
FILE_ADMIN = 'admin.csv'
ANALISTAS_FOCO = ['Adriel', 'Isabella', 'Guilherme']

def load_and_clean_data():
    # Carregar Admin
    df_adm = pd.read_csv(FILE_ADMIN)
    df_adm['Cadastro'] = pd.to_datetime(df_adm['Cadastro'], errors='coerce')
    df_adm['Data_Última_Msg'] = pd.to_datetime(df_adm['Data_Última_Msg'], errors='coerce')
    
    # Extração de Turma/Produto
    def get_info(nome):
        nome = str(nome).upper()
        produto = "OUTROS"
        for p in ['MBA', 'CPA', 'CEA', 'CFP']:
            if p in nome: produto = p; break
        turma = "Geral"
        if ' T' in nome:
            idx = nome.find(' T')
            turma = nome[idx+1:idx+4].strip()
        return pd.Series([produto, turma])

    df_adm[['Produto', 'Turma']] = df_adm['Nome'].apply(get_info)

    # Health Score Lógico
    hoje = df_adm['Data_Última_Msg'].max()
    df_adm['Dias_Inativo'] = (hoje - df_adm['Data_Última_Msg']).dt.days
    df_adm['Health_Score'] = df_adm['Dias_Inativo'].apply(
        lambda x: 'Crítico (Vermelho)' if x > 15 else ('Atenção (Amarelo)' if x > 7 else 'Saudável (Verde)')
    )

    # Carregar Suporte
    df_sup = pd.read_csv(FILE_SUPORTE)
    df_sup['created'] = pd.to_datetime(df_sup['created'], errors='coerce')
    
    # Simulação de SLA (Ajuste conforme sua regra de negócio real)
    if 'SLA_First_Resp' not in df_sup.columns:
        df_sup['SLA_First_Resp'] = np.random.choice(['Dentro', 'Fora'], len(df_sup), p=[0.85, 0.15])
    
    return df_adm, df_sup

df_adm, df_sup = load_and_clean_data()

# ==========================================
# 2. LAYOUT DO DASHBOARD
# ==========================================
app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

sidebar = html.Div([
    html.H2("Filtros BI", className="display-6"),
    html.Hr(),
    html.P("Selecione o Produto e Turma:"),
    dcc.Dropdown(
        id='filtro-produto',
        options=[{'label': i, 'value': i} for i in sorted(df_adm['Produto'].unique())],
        value=None, placeholder="Todos os Produtos"
    ),
    html.Br(),
    dcc.Dropdown(
        id='filtro-turma',
        options=[{'label': i, 'value': i} for i in sorted(df_adm['Turma'].unique())],
        value=None, placeholder="Todas as Turmas"
    ),
    html.Hr(),
    html.Div([
        html.Img(src="https://eumebanco.com.br/wp-content/uploads/2022/08/logo-eu-me-banco.png", style={'width': '100%'})
    ], className="mt-5")
], style={"position": "fixed", "top": 0, "left": 0, "bottom": 0, "width": "18rem", "padding": "2rem 1rem", "background-color": "#f8f9fa"})

content = html.Div([
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Total de Alunos", className="card-title"),
                html.H2(id="card-alunos", className="text-primary")
            ])
        ])),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("SLA (1ª Resposta)", className="card-title"),
                html.H2(id="card-sla", className="text-success")
            ])
        ])),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Health Score Crítico", className="card-title"),
                html.H2(id="card-health", className="text-danger")
            ])
        ])),
    ], className="mb-4"),

    dbc.Tabs([
        dbc.Tab(label="Operação & SLA", children=[
            dbc.Row([
                dbc.Col(dcc.Graph(id='graph-volume-diario'), md=8),
                dbc.Col(dcc.Graph(id='graph-pizza-analistas'), md=4),
            ], className="mt-4"),
        ]),
        dbc.Tab(label="Acadêmico & Retenção", children=[
            dbc.Row([
                dbc.Col(dcc.Graph(id='graph-health-dist'), md=6),
                dbc.Col(dcc.Graph(id='graph-engajamento-turma'), md=6),
            ], className="mt-4"),
        ]),
    ])
], style={"margin-left": "20rem", "padding": "2rem"})

app.layout = html.Div([sidebar, content])

# ==========================================
# 3. INTERATIVIDADE (CALLBACKS)
# ==========================================
@callback(
    [Output('card-alunos', 'children'),
     Output('card-sla', 'children'),
     Output('card-health', 'children'),
     Output('graph-volume-diario', 'figure'),
     Output('graph-pizza-analistas', 'figure'),
     Output('graph-health-dist', 'figure'),
     Output('graph-engajamento-turma', 'figure')],
    [Input('filtro-produto', 'value'),
     Input('filtro-turma', 'value')]
)
def update_dashboard(prod, turma):
    # Filtragem Dinâmica
    dff_adm = df_adm.copy()
    dff_sup = df_sup.copy()

    if prod:
        dff_adm = dff_adm[dff_adm['Produto'] == prod]
    if turma:
        dff_adm = dff_adm[dff_adm['Turma'] == turma]

    # KPIs
    total_alunos = len(dff_adm)
    
    # Cálculo real do SLA
    if len(dff_sup) > 0:
        sla_calc = (dff_sup['SLA_First_Resp'] == 'Dentro').sum() / len(dff_sup)
        sla_pct = f"{sla_calc:.1%}"
    else:
        sla_pct = "0%"

    criticos = len(dff_adm[dff_adm['Health_Score'] == 'Crítico (Vermelho)'])

    # Grafico Volume Diário
    vol_dia = dff_sup.groupby(dff_sup['created'].dt.date).size().reset_index(name='Tickets')
    fig_vol = px.line(vol_dia, x='created', y='Tickets', title="Demanda Diária", template="plotly_white")

    # Grafico Analistas
    analistas_counts = dff_sup[dff_sup['responsavel'].isin(ANALISTAS_FOCO)]['responsavel'].value_counts().reset_index()
    fig_ana = px.pie(analistas_counts, values='count', names='responsavel', title="Carga por Analista", hole=0.3)

    # Grafico Health Score (Correção do Erro de Index)
    health_data = dff_adm['Health_Score'].value_counts().reset_index()
    health_data.columns = ['Status', 'Total'] # Nomeando colunas explicitamente
    fig_health = px.bar(
        health_data, x='Status', y='Total', color='Status', 
        title="Saúde da Base",
        color_discrete_map={
            'Saudável (Verde)': '#28a745',
            'Atenção (Amarelo)': '#ffc107',
            'Crítico (Vermelho)': '#dc3545'
        }
    )

    # Engajamento
    fig_eng = px.histogram(dff_adm, x='Dias_Inativo', nbins=20, title="Dias desde o último contato")

    return f"{total_alunos}", sla_pct, f"{criticos}", fig_vol, fig_ana, fig_health, fig_eng

if __name__ == '__main__':
    app.run(debug=True, port=8050)