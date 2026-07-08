import streamlit as st
import pypdf
import re
import pandas as pd

def extrair_codigo_solo(texto_linha):
    """Identifica a ordem de predominância do solo na linha analisada"""
    desc_lower = texto_linha.lower()
    
    # Mapeamento dos componentes: 1=Areia, 2=Silte, 3=Argila
    pesos = {'argil': 3, 'silt': 2, 'arei': 1}
    
    # Encontra os termos na ordem exata em que aparecem na frase
    termos_encontrados = re.findall(r'(argil|silt|arei)', desc_lower)
    
    componentes = []
    for termo in termos_encontrados:
        num = pesos[termo]
        if num not in componentes:
            componentes.append(num)
            
    # Se não achou nenhum componente de solo na linha, retorna 000
    if not componentes:
        return 0
        
    # Preenche com zeros à direita se houver menos de 3 componentes (ex: argila arenosa = 310)
    while len(componentes) < 3:
        componentes.append(0)
        
    return int(f"{componentes[0]}{componentes[1]}{componentes[2]}")

def extrair_spt_da_linha(texto_linha, metro_alvo):
    """Tenta capturar o valor do SPT associado àquela linha/metro"""
    # Remove o número do metro do início para não confundir com o SPT
    texto_filtrado = re.sub(rf'^\b{metro_alvo}\b', '', texto_linha.strip())
    
    # Encontra todos os números restantes na linha
    numeros = re.findall(r'\b\d+\b', texto_filtrado)
    
    if numeros:
        # Geralmente o SPT é o último número da linha ou um valor coerente (ex: entre 0 e 60)
        for num in reversed(numeros):
            valor = int(num)
            if 0 <= valor <= 70: # Filtro para evitar pegar anos (ex: 2026) ou números de furos
                return valor
    return "-"

def processar_sondagem_sequencial(pdf_file):
    reader = pypdf.PdfReader(pdf_file)
    texto_completo = ""
    
    for page in reader.pages:
        texto = page.extract_text()
        if texto:
            texto_completo += texto + "\n"
            
    linhas = texto_completo.split('\n')
    
    # Mapeia o que foi encontrado para cada metro detectado no PDF
    banco_de_linhas = {}
    
    for linha in linhas:
        linha_limpa = linha.strip()
        if not linha_limpa:
            continue
            
        # Procura por números no início da linha ou isolados que indiquem a profundidade
        numeros = re.findall(r'\b\d+\b', linha_limpa)
        if numeros:
            # Testa se o primeiro número pode ser o metro correspondente
            metro_detectado = int(numeros[0])
            if 1 <= metro_detectado <= 60: # Limite seguro de profundidade de sondagem
                # Se a linha falar de solo, guarda essa linha para este metro
                if any(k in linha_limpa.lower() for k in ['argil', 'silt', 'arei']):
                    banco_de_linhas[metro_detectado] = linha_limpa

    # Se não mapeou nada direto, faz uma busca mais flexível por varredura de texto
    if not banco_de_linhas:
        for metro in range(1, 40):
            for linha in linhas:
                # Procura linhas que começam com o número do metro ou contém "Xm " ou "X m "
                if re.search(rf'(?:\b{metro}\s*m\b|^\s*{metro}\b)', linha.lower()):
                    if any(k in linha.lower() for k in ['argil', 'silt', 'arei']):
                        banco_de_linhas[metro] = linha
                        break

    # Monta o resultado final metro a metro de forma estritamente sequencial
    dados_finais = []
    max_metro = max(banco_de_linhas.keys()) if banco_de_linhas else 20 # vai até o último encontrado ou padrão 20m
    
    for m in range(1, max_metro + 1):
        if m in banco_de_linhas:
            linha_texto = banco_de_linhas[m]
            codigo_solo = extrair_codigo_solo(linha_texto)
            spt = extrair_spt_da_linha(linha_texto, m)
            desc_solo = re.sub(r'\d+', '', linha_texto).replace('m', '').strip()
        else:
            # Caso o PDF pule algum metro na escrita, ele mantém a sequência zerada
            codigo_solo = "---"
            spt = "-"
            desc_solo = "Não identificado nesta profundidade"
            
        dados_finais.append({
            "Metro_Int": m,
            "Formato_Texto": f"{m}m - {codigo_solo}  (SPT: {spt})",
            "Metro": f"{m}m",
            "Código": codigo_solo,
            "SPT": spt,
            "Texto Original da Linha": desc_solo
        })
        
    return dados_finais, texto_completo

# --- Interface Web ---
st.set_page_config(page_title="Leitor de Sondagem SPT", layout="wide", page_icon="📊")

st.title("📊 Leitor Inteligente de Sondagem (SPT)")
st.write("Insira o PDF do seu relatório para gerar o perfil geológico estritamente metro a metro.")

st.info("💡 **Regra do Código:** 1 = Areia | 2 = Silte | 3 = Argila  \n*Exemplos:* Argila silto-arenosa = `321` | Argila arenosa = `310` | Silte argiloso = `230`")

uploaded_file = st.file_uploader("Escolha o arquivo PDF da Sondagem", type="pdf")

if uploaded_file is not None:
    with st.spinner("Decodificando e ordenando a sequência metro a metro..."):
        dados, texto_bruto = processar_sondagem_sequencial(uploaded_file)
        
    if dados:
        st.success("PDF processado com sucesso!")
        
        # --- EXIBIÇÃO NO FORMATO EXATO QUE VOCÊ PEDIU ---
        st.subheader("📝 Resultado Final Metro a Metro")
        
        # Cria um bloco de texto com a formatação exata desejada pelo usuário
        linhas_texto_formatado = [d["Formato_Texto"] for d in dados]
        resultado_textarea = "\n".join(linhas_texto_formatado)
        
        # Exibe em uma caixa de texto grande pronta para copiar
        st.text_area("Resultado formatado (Copie daqui):", value=resultado_textarea, height=350)
        
        # Também mostra em formato de tabela estruturada para conferência rápida
        with st.expander("📊 Visualizar em formato de Tabela"):
            df = pd.DataFrame(dados).drop(columns=["Metro_Int", "Formato_Texto"])
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Baixar Planilha Excel/CSV", csv, "sondagem_sequencial.csv", "text/csv")
            
    else:
        st.error("Não foi possível ler os dados sequenciais. Verifique o texto extraído abaixo.")
        
    with St.expander("🔍 Inspecionar Texto Bruto Extraído do PDF"):
        if texto_bruto.strip() == "":
            st.warning("⚠️ O texto veio em branco! O PDF é uma imagem (foto/escaneado). Passe ele em um leitor de OCR antes (como o ilovepdf.com/pt/ocr-pdf).")
        else:
            St.text(texto_bruto)
