import streamlit as st
import pypdf
import re
import pandas as pd

def extrair_codigo_solo(descricao):
    """Transforma a descrição do solo no código de predominância (ex: 321)"""
    desc_lower = descricao.lower()
    
    # Mapeamento inicial dos componentes
    pesos = {'argil': 3, 'silt': 2, 'arei': 1}
    
    # Encontra os componentes na ordem em que aparecem no texto
    termos_encontrados = re.findall(r'(argil|silt|arei)', desc_lower)
    
    # Remove duplicatas mantendo a ordem de aparição
    componentes = []
    for termo in termos_encontrados:
        num = pesos[termo]
        if num not in componentes:
            componentes.append(num)
            
    # Preenche com zeros as posições vazias (até ter 3 dígitos)
    while len(componentes) < 3:
        componentes.append(0)
        
    return int(f"{componentes[0]}{componentes[1]}{componentes[2]}")

def processar_pdf_sondagem(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    texto_completo = ""
    
    # Extrai o texto de todas as páginas
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"
        
    dados_finais = []
    
    # Tenta capturar padrões comuns de tabelas de sondagem:
    # Ex: "1 Argila silto-arenosa 12", "2m Silte argiloso 8", "3 metros Areia 15"
    padrao_linha = re.compile(r'(\d+)\s*(?:m|metro|metros)?\s+([A-Za-záéíóúçãõ\s-]+?)\s+(\d+)\s*$', re.MULTILINE)
    linhas_encontradas = padrao_linha.findall(texto_completo)
    
    # Se falhar, tenta buscar em blocos de texto contínuos por linha
    if not linhas_encontradas:
        linhas = texto_completo.split('\n')
        for linha in lines:
            # Procura por números isolados que indicam profundidade e SPT nas pontas
            partes = re.findall(r'\b\d+\b', linha)
            if len(partes) >= 2:
                # Procura se há palavras chave de solo na linha
                if any(k in linha.lower() for k in ['argil', 'silt', 'arei']):
                    metro = partes[0]
                    spt = partes[-1]
                    # Limpa o texto para pegar a descrição do solo
                    desc = re.sub(r'\b\d+\b', '', linha).strip()
                    linhas_encontradas.append((metro, desc, spt))

    for metro, descricao, spt in linhas_encontradas:
        if any(k in descricao.lower() for k in ['argil', 'silt', 'arei']):
            codigo_solo = extrair_codigo_solo(descricao)
            dados_finais.append({
                "Metro": int(metro),
                "Descrição do Solo": descricao.strip(),
                "Código Predominante": codigo_solo,
                "SPT": int(spt)
            })
            
    # Ordena os metros para garantir a sequência correta de 1 a 1
    if dados_finais:
        dados_finais = sorted(dados_finais, key=lambda x: x['Metro'])
        for d in dados_finais:
            d['Metro'] = f"{d['Metro']}m"
            
    return dados_finais, texto_completo

# --- Interface Web ---
st.set_page_config(page_title="Leitor de Sondagem SPT", layout="wide", page_icon="📊")

st.title("📊 Leitor Inteligente de Sondagem (SPT)")
st.write("Insira o PDF do seu relatório de sondagem para traduzir o perfil geológico metro a metro.")

st.info("💡 **Regra do Código:** 1 = Areia | 2 = Silte | 3 = Argila (Exemplo: Argila silto-arenosa = 321)")

uploaded_file = st.file_uploader("Escolha o arquivo PDF da Sondagem", type="pdf")

if uploaded_file is not None:
    with st.spinner("Processando e decodificando o arquivo..."):
        dados, texto_bruto = processar_pdf_sondagem(uploaded_file)
        
    if dados:
        df = pd.DataFrame(dados)
        st.success("PDF processado com sucesso!")
        
        # Exibição da tabela gerada
        st.subheader("📋 Relatório Metro a Metro")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Botão para baixar em Excel/CSV
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Baixar Planilha (CSV)", csv, "sondagem_processada.csv", "text/csv")
    else:
        st.error("Não conseguimos extrair as linhas automaticamente. O PDF pode ser uma imagem digitalizada ou o formato do texto é muito diferente.")
        
    with st.expander("🔍 Inspecionar Texto Extraído do PDF (Para Ajustes)"):
        st.text(texto_bruto)
