import streamlit as st
import pypdf
import re
import pandas as pd

def extrair_codigo_solo(descricao):
    desc_lower = descricao.lower()
    pesos = {'argil': 3, 'silt': 2, 'arei': 1}
    
    # Encontra os termos na ordem em que aparecem na frase
    termos_encontrados = re.findall(r'(argil|silt|arei)', desc_lower)
    
    componentes = []
    for termo in termos_encontrados:
        num = pesos[termo]
        if num not in componentes:
            componentes.append(num)
            
    while len(componentes) < 3:
        componentes.append(0)
        
    return int(f"{componentes[0]}{componentes[1]}{componentes[2]}")

def processar_pdf_sondagem_avancado(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    texto_completo = ""
    
    for page in reader.pages:
        texto = page.extract_text()
        if texto:
            texto_completo += texto + "\n"
        
    dados_finais = []
    linhas = texto_completo.split('\n')
    
    for linha in linhas:
        linha_limpa = linha.strip()
        if not linha_limpa:
            continue
            
        # Verifica se a linha contém palavras-chave de solo
        tem_solo = any(k in linha_limpa.lower() for k in ['argil', 'silt', 'arei'])
        
        if tem_solo:
            # Encontra todos os números isolados na linha
            numeros = re.findall(r'\b\d+\b', linha_limpa)
            
            if len(numeros) >= 2:
                # Na maioria dos relatórios: o primeiro número costuma ser o Metro
                # e um dos últimos números (ou o último) é o SPT total.
                metro = int(numeros[0])
                spt = int(numeros[-1]) # Pega o último número da linha como SPT
                
                # Se o último número parecer muito alto para ser SPT (ex: ano ou número de furo), tenta o penúltimo
                if spt > 80 and len(numeros) >= 3:
                    spt = int(numeros[-2])
                
                # Remove os números do texto para isolar a descrição do solo
                descricao = linha_limpa
                for n in numeros:
                    descricao = re.sub(rf'\b{n}\b', '', descricao)
                descricao = re.sub(r'\s+', ' ', descricao).strip()
                
                # Evita pegar metros falsos (ex: profundidades absurdas ou erros de leitura)
                if 0 <= metro <= 100: 
                    codigo_solo = extrair_codigo_solo(linha_limpa)
                    dados_finais.append({
                        "Metro_Int": metro,
                        "Metro": f"{metro}m",
                        "Descrição do Solo": descricao if descricao else "Identificado por palavras-chave",
                        "Código Predominante": codigo_solo,
                        "SPT": spt
                    })

    # Remove duplicatas de metros (caso ele leia a mesma linha duas vezes) e ordena
    if dados_finais:
        df_temp = pd.DataFrame(dados_finais)
        df_temp = df_temp.drop_duplicates(subset=['Metro_Int'], keep='first')
        df_temp = df_temp.sort_values(by='Metro_Int')
        return df_temp.drop(columns=['Metro_Int']).to_dict(orient='records'), texto_completo
            
    return [], texto_completo

# --- Interface Web ---
st.set_page_config(page_title="Leitor de Sondagem SPT", layout="wide", page_icon="📊")

st.title("📊 Leitor Inteligente de Sondagem (SPT)")
st.write("Insira o PDF do seu relatório de sondagem para traduzir o perfil geológico metro a metro.")
st.info("💡 **Regra do Código:** 1 = Areia | 2 = Silte | 3 = Argila (Exemplo: Argila silto-arenosa = 321)")

uploaded_file = st.file_uploader("Escolha o arquivo PDF da Sondagem", type="pdf")

if uploaded_file is not None:
    with st.spinner("Processando documento..."):
        dados, texto_bruto = processar_pdf_sondagem_avancado(uploaded_file)
        
    if dados:
        df = pd.DataFrame(dados)
        st.success("PDF processado com sucesso!")
        st.subheader("📋 Relatório Metro a Metro")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Baixar Planilha (CSV)", csv, "sondagem_processada.csv", "text/csv")
    else:
        st.error("Não conseguimos extrair as linhas automaticamente. Verifique o texto extraído abaixo para entender o motivo.")
        
    with st.expander("🔍 Inspecionar Texto Extraído do PDF (Fundamental para Ajustes)"):
        if texto_bruto.strip() == "":
            st.warning("⚠️ O TEXTO EXTRAÍDO ESTÁ TOTALMENTE VAZIO! O seu PDF é uma imagem digitalizada (escaneada). O sistema precisa de OCR para ler imagens.")
        else:
            st.text(texto_bruto)
