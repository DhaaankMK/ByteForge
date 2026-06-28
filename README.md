# ByteForge

Software desktop profissional para geração de arquivos de preenchimento
(*dummy files*) de qualquer tamanho, recheados com dados pseudoaleatórios
de alta entropia e marcas d'água internas para identificação.

Desenvolvido por **DhaaankMK**.

---

## 1. Arquitetura do projeto

O código é modularizado em dois pacotes principais, separando claramente
a lógica de backend da interface gráfica:

```
ByteForge/
├── main.py                     # Ponto de entrada da aplicação
├── requirements.txt
├── core/                       # Backend (sem nenhuma dependência de GUI)
│   ├── paths.py                 # Caminhos centralizados (data/, logs/, output/)
│   ├── app_logger.py            # Logging persistente (início/fim/erros)
│   ├── disk_utils.py            # Verificação segura de espaço em disco
│   ├── file_generator.py        # Geração do arquivo em thread + watermark fixa
│   ├── settings_manager.py      # Configurações persistentes (config.json)
│   ├── terms_manager.py         # Termo de Responsabilidade (aceite único)
│   ├── file_registry.py         # Histórico/registro de arquivos gerados
│   ├── network_utils.py         # Simulação de conexão com a Loja de Plugins
│   └── plugin_manager.py        # Descoberta e execução de plugins .py
├── gui/                         # Frontend (CustomTkinter)
│   ├── app.py                    # Janela principal e TabView
│   ├── dialog_terms.py           # Diálogo modal do Termo de Responsabilidade
│   ├── dialog_resize.py          # Diálogo modal para editar tamanho de arquivo
│   ├── tab_home.py               # Aba de geração de arquivos
│   ├── tab_plugins.py            # Aba da Loja de Plugins
│   ├── tab_manager.py            # Aba do Gerenciador de Arquivos
│   ├── tab_credits.py            # Aba de créditos (com easter egg)
│   └── tab_settings.py           # Aba de configurações avançadas
├── data/                        # Criada automaticamente (config + registro)
├── logs/                        # Criada automaticamente (logs persistentes)
├── output/                      # Pasta padrão de salvamento dos arquivos
├── plugins/                     # Pasta vazia por padrão (plugins do usuário)
└── examples_plugins/            # Plugin de exemplo (copie para /plugins)
```

## 2. Instalação e execução

```bash
# 1. Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute a aplicação
python main.py
```

Na primeira execução, o **Termo de Responsabilidade** será exibido em
uma janela modal. É necessário marcar a caixa de concordância e clicar
em "Concordar e Continuar" para liberar o uso do aplicativo. Esse aceite
é salvo permanentemente em `data/terms_acceptance.json` e não será
solicitado novamente, a menos que o termo seja atualizado para uma nova
versão.

## 3. Funcionalidades principais

- **Segurança de disco (com piso absoluto)**: antes de iniciar qualquer
  geração, o ByteForge verifica (via `psutil`/`shutil`) o espaço livre no
  diretório de destino e bloqueia a operação caso o espaço restante após
  a escrita fique abaixo do limite configurado. Esse limite é ajustável
  na aba Configurações, mas **nunca pode ficar abaixo de 5 GB**,
  independentemente do valor digitado pelo usuário — um piso de
  segurança aplicado automaticamente em código.
- **Performance**: a escrita ocorre em blocos (*chunks*, configuráveis)
  dentro de uma `threading.Thread` dedicada, mantendo a interface sempre
  responsiva — incluindo suporte a pausa e cancelamento durante a operação.
- **Marca d'água permanente e imutável**: todo arquivo gerado contém,
  internamente, a assinatura fixa **"ByteForge - DhaaankMK"** junto com
  metadados em JSON (data de geração, índice do bloco). Essa assinatura
  **não pode ser alterada pelo usuário** em nenhuma tela — é exibida na
  aba Configurações apenas como informação somente leitura. Os nomes de
  arquivo sugeridos por padrão também carregam essa mesma marca.
- **Local de salvamento configurável**: por padrão, os arquivos são
  salvos dentro da própria pasta do ByteForge (`output/`), mas o usuário
  pode escolher qualquer outra pasta na aba Configurações.
- **Configurações persistentes**: todas as preferências (pasta padrão,
  tema, comportamento, limites de segurança) são salvas em
  `data/config.json` e recarregadas automaticamente a cada execução.
- **Termo de Responsabilidade obrigatório**: o uso do aplicativo só é
  liberado após o aceite explícito (checkbox + botão), exigido apenas
  uma vez por versão do termo.
- **Gerenciador de Arquivos**: nova aba que lista todos os arquivos já
  gerados pelo ByteForge (incluindo o total histórico de criações),
  permite abrir a pasta, editar o tamanho de um arquivo existente
  (regeneração com nova marca d'água) e excluir arquivos diretamente
  pela interface — inclusive identificando arquivos que foram movidos
  ou apagados manualmente fora do aplicativo (status "Ausente").
- **Logs persistentes e rotativos**: toda execução (início e
  encerramento) é registrada em `logs/byteforge.log`, com rotação
  automática por tamanho. Qualquer erro não tratado em qualquer parte
  da aplicação é automaticamente capturado e registrado no log.
- **Arquitetura de plugins**: a aplicação varre a pasta `plugins/` em
  busca de arquivos `.py`. Caso nenhum seja encontrado, exibe o painel
  "Loja de Plugins: Em breve" com uma animação de spinner.
- **Créditos com easter egg**: na aba Créditos, clique na logomarca para revelar (com uma animação de pulso e entrada deslizante) o painel de créditos completos a **DhaaankMK**.
- **Identidade visual de marca**: toda a interface usa uma paleta extraída diretamente da logomarca oficial (gradiente preto → azul-índigo), com uma tela de splash animada na abertura, cabeçalhos com gradiente em cada aba, barra de progresso com animação suave e pequenos efeitos de destaque (flash de sucesso) — tudo isso puramente visual, sem qualquer alteração na lógica funcional do aplicativo.

## 3.1. Assets visuais

A pasta `assets/` contém a identidade visual oficial do projeto:

```
assets/
├── logo.png   # Logomarca (520x520px) — usada no cabeçalho, splash, créditos e ícone da janela
└── capa.png   # Arte de capa (1280x720px) — usada como ilustração na aba Home
```

Caso esses arquivos sejam removidos ou renomeados, a interface continua funcionando normalmente — todos os componentes visuais (`gui/widgets.py`, `gui/splash.py`) foram escritos para degradar graciosamente (omitindo a imagem) caso o asset não seja encontrado.

## 4. Testando o plugin de exemplo

Para validar a arquitetura de plugins, copie o arquivo de exemplo para a
pasta correta e reabra (ou atualize) a aba Plugins:

```bash
cp examples_plugins/exemplo_info_sistema.py plugins/
```

## 5. Compilando um executável único com PyInstaller

O PyInstaller permite empacotar o ByteForge em um único arquivo
executável (`.exe` no Windows, binário no Linux/macOS), sem exigir que o
usuário final tenha Python instalado.

### 5.1. Instalação do PyInstaller

Já incluído em `requirements.txt`. Caso necessário, instale manualmente:

```bash
pip install pyinstaller
```

### 5.2. Comando de build recomendado

A partir da raiz do projeto (onde está o `main.py`), execute:

```bash
pyinstaller --onefile --noconsole --name ByteForge --icon=assets/byteforge.ico main.py
```

Explicação de cada flag:

| Flag | Finalidade |
|---|---|
| `--onefile` | Empacota tudo (código + dependências) em um único arquivo executável, facilitando a distribuição. |
| `--noconsole` | Remove a janela de terminal/console ao abrir a aplicação, mantendo apenas a interface gráfica (visual limpo). Em alguns sistemas, equivalente a `--windowed`. |
| `--name ByteForge` | Define o nome do executável final (`ByteForge.exe` no Windows). |
| `--icon=assets/byteforge.ico` | Define o ícone customizado do executável. **O arquivo precisa estar no formato `.ico` no Windows** (no macOS, utilize `.icns`). |

### 5.3. Observações importantes sobre o `customtkinter`

O `customtkinter` depende de arquivos de tema (`.json`) embutidos no
próprio pacote. Em alguns ambientes, o PyInstaller pode não detectar
automaticamente esses arquivos de dados. Caso a interface abra sem
estilos aplicados após a compilação, adicione a flag `--collect-data`:

```bash
pyinstaller --onefile --noconsole --name ByteForge ^
    --icon=assets/byteforge.ico ^
    --collect-data customtkinter ^
    main.py
```

(No Linux/macOS, substitua o `^` de quebra de linha por `\`.)

### 5.3.1. Persistência de dados no executável compilado (`--onefile`)

O modo `--onefile` extrai o conteúdo do executável para uma pasta
temporária a cada execução, pasta essa que é **apagada** ao encerrar o
programa. Por esse motivo, o módulo `core/paths.py` foi projetado para
detectar automaticamente quando está rodando como executável compilado
(`sys.frozen`) e, nesse caso, salvar as pastas `data/`, `logs/` e
`output/` ao lado do próprio arquivo `ByteForge.exe` — e não dentro da
pasta temporária — garantindo que configurações, histórico de arquivos
e logs sejam preservados entre execuções.

Na prática, isso significa que após a primeira execução do executável
compilado, surgirão automaticamente as pastas `data/`, `logs/` e
`output/` ao lado de `ByteForge.exe`. Essas pastas devem acompanhar o
executável caso ele seja movido para outro local ou computador.

### 5.4. Localização do executável gerado

Após a compilação, o executável final estará disponível em:

```
dist/ByteForge.exe      # Windows
dist/ByteForge          # Linux/macOS
```

A pasta `build/` e o arquivo `ByteForge.spec` gerados durante o processo
podem ser apagados com segurança após a conclusão do build; eles são
apenas artefatos intermediários do PyInstaller.

### 5.5. Distribuição

Como a flag `--onefile` empacota tudo em um único binário, basta
distribuir o arquivo gerado em `dist/`. As pastas `data/`, `logs/` e
`output/` são criadas automaticamente ao lado do executável na primeira
execução — não é necessário criá-las manualmente. Caso você queira
distribuir plugins adicionais junto com o executável compilado, crie uma
pasta `plugins/` no mesmo diretório do executável final e coloque os
arquivos `.py` lá dentro.

## 6. Aviso de segurança e uso responsável

O ByteForge gera arquivos grandes propositalmente para fins de
preenchimento de disco, testes de backup, simulação de carga de
armazenamento, entre outros usos legítimos. **O limite mínimo de 15 GB
de espaço livre obrigatório existe justamente para impedir que o
software, por erro de operação, deixe o sistema do usuário sem espaço
suficiente para funcionar corretamente.** Esse limite é configurável na
aba "Configurações", mas a recomendação é mantê-lo em um valor seguro
para o seu sistema operacional.
