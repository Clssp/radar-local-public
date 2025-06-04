import pdfkit

# Força o caminho do wkhtmltopdf manualmente
config = pdfkit.configuration(wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')

# HTML de exemplo
html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Relatório de Concorrência</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        h1 { color: #004080; }
        .box { border: 1px solid #ddd; margin-bottom: 10px; padding: 10px; }
    </style>
</head>
<body>
    <h1>Relatório de Concorrência</h1>
    <p><strong>Profissão:</strong> Barbearia</p>
    <p><strong>Localização:</strong> Cotia</p>

    <div class="box">
        <h3>Concorrente: La Barba Barber Shop</h3>
        <p><strong>Nota:</strong> 4.7</p>
        <p><strong>Endereço:</strong> Rua Exemplo, Cotia - SP</p>
        <p><strong>Comentários:</strong></p>
        <ul>
            <li>Atendimento excelente</li>
            <li>Ambiente limpo</li>
        </ul>
    </div>

    <h2>Análise Inteligente</h2>
    <p><strong>Elogios:</strong> Atendimento e ambiente</p>
    <p><strong>Críticas:</strong> Preço um pouco alto</p>
    <p><strong>Sugestões:</strong> Oferecer cortes promocionais, melhorar tempo de espera, usar redes sociais</p>
</body>
</html>
"""

# Gera o PDF
pdfkit.from_string(html, "relatorio_concorrencia.pdf", configuration=config)

print("✅ PDF gerado com sucesso!")