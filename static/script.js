let cacheEmprestimos = [];
let sincronizadorId = null;
let instanciaGrafico = null;

function executarLogin() {
    const usuario = document.getElementById('login-user').value.trim();
    const senha = document.getElementById('login-pass').value.trim();

    fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario, senha })
    })
    .then(res => { if(!res.ok) throw new Error(); return res.json(); })
    .then(data => {
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('user-display').innerText = data.usuario;
        document.getElementById('app').style.display = 'flex';
        enviarMensagemToast("Autenticação validada via servidor!", "success");
        sincronizarNucleoDashboard();
        sincronizadorId = setInterval(sincronizarNucleoDashboard, 4000);
    })
    .catch(() => enviarMensagemToast("Falha na autenticação corporativa.", "error"));
}

function executarLogout() {
    fetch('/api/logout', { method: 'POST' }).then(() => {
        clearInterval(sincronizadorId);
        document.getElementById('app').style.display = 'none';
        document.getElementById('login-screen').style.display = 'flex';
    });
}

function sincronizarNucleoDashboard() {
    fetch('/api/dashboard')
    .then(res => { if(res.status === 401) executarLogout(); return res.json(); })
    .then(data => {
        if (!data) return;
        cacheEmprestimos = data.emprestimos;
        
        document.getElementById('count-uso').innerText = data.total_emprestados;
        document.getElementById('count-disponiveis').innerText = 40 - data.total_emprestados;
        document.getElementById('log-qty').innerText = data.logs.length;

        filtrarGradeEmprestimos();
        renderizarTabelaAuditoria(data.logs);
        processarGraficoBI(data.grafico_salas);
    }).catch(() => console.log("Aguardando rede..."));
}

function filtrarGradeEmprestimos() {
    const termo = document.getElementById('campo-busca').value.toLowerCase().trim();
    const tabela = document.getElementById('tabela-emprestimos-corpo');
    if (!tabela) return;

    const filtrados = cacheEmprestimos.filter(emp => 
        emp.aluno.toLowerCase().includes(termo) || 
        emp.notebook.toLowerCase().includes(termo) || 
        (emp.sala_aluno && emp.sala_aluno.toLowerCase().includes(termo))
    );

    if (filtrados.length === 0) {
        tabela.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:15px; color:gray;">Nenhum empréstimo ativo localizado.</td></tr>`;
        return;
    }

    tabela.innerHTML = filtrados.map(emp => `
        <tr>
            <td><span class="badge em-uso" style="background:#e8f5e9; color:#2e7d32; padding:3px 6px; border-radius:4px; font-size:11px;">${emp.sala_aluno || 'Geral'}</span></td>
            <td><strong>${emp.aluno}</strong></td>
            <td><code>${emp.notebook}</code></td>
            <td><span class="badge analise" style="background:#f0f4f8; color:#37474f; padding:3px 6px; border-radius:4px; font-size:11px;">${emp.local_notebook || 'Armário'}</span></td>
            <td>
                <button class="btn-table btn-edit" onclick="abrirModalEdicao(${emp.id})">Editar</button>
                <button class="btn-table btn-delete" onclick="removerRegistroEmprestimo(${emp.id})">Excluir</button>
            </td>
        </tr>
    `).join('');
}

function renderizarTabelaAuditoria(logs) {
    const tabela = document.getElementById('tabela-logs-corpo');
    if (!tabela) return;

    if (logs.length === 0) {
        tabela.innerHTML = `<tr><td colspan="3" style="text-align:center; padding:15px; color:gray;">Nenhum sinal ativo na rede.</td></tr>`;
        return;
    }

    tabela.innerHTML = logs.map(log => {
        const uLower = log.usuario_windows.toLowerCase();
        const ehAdmin = uLower.includes("admin") || uLower.includes("suporte");
        const st = ehAdmin ? "background:#fff7ed; color:#c2410c; border:1px solid #fed7aa; padding:2px 6px; border-radius:4px;" : "background:#f0fdf4; color:#166534; padding:2px 6px; border-radius:4px;";
        
        return `
            <tr>
                <td><strong>${log.notebook}</strong></td>
                <td><span class="badge" style="font-size:11px; ${st}">${ehAdmin ? '⚠️':'👤'} ${log.usuario_windows}</span></td>
                <td style="font-size:11px; font-family:monospace; color:gray;">${log.horario.split(' ')[1]} <small style="display:block; color:var(--text-light); font-family:'Inter'">${calcularTempoRelativo(log.horario)}</small></td>
            </tr>
        `;
    }).join('');
}

function exportarRelatorioCSV() {
    if(cacheEmprestimos.length === 0) return enviarMensagemToast("Sem dados para exportar", "error");
    let csv = "ID,Sala,Aluno,Notebook,Localizacao,Data\n";
    cacheEmprestimos.forEach(e => {
        csv += `${e.id},"${e.sala_aluno}","${e.aluno}",${e.notebook},"${e.local_notebook}",${e.data_retirada}\n`;
    });
    let blob = new Blob(["\ufeff" + csv], { type: 'text/csv;charset=utf-8;' });
    let link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", `relatorio_geni_${new Date().toLocaleDateString().replace(/\//g,'-')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function processarGraficoBI(dados) {
    const ctx = document.getElementById('graficoDemandas');
    if (!ctx) return;
    
    const labels = dados.map(d => d.sala || "Não Informada");
    const valores = dados.map(d => d.qtd);

    if (instanciaGrafico) {
        instanciaGrafico.data.labels = labels;
        instanciaGrafico.data.datasets[0].data = valores;
        instanciaGrafico.update();
    } else {
        instanciaGrafico = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{ label: 'Qtd Requisições', data: valores, backgroundColor: '#1976d2', borderRadius: 6 }]
            },
            options: { responsive: true, scales: { y: { beginAtZero: true } } }
        });
    }
}

function calcularTempoRelativo(dataStr) {
    try {
        const partes = dataStr.split(' ');
        const d = partes[0].split('/'), h = partes[1].split(':');
        const diff = Math.floor((new Date() - new Date(d[2], d[1]-1, d[0], h[0], h[1], h[2])) / 1000);
        if (diff < 15) return "agora mesmo";
        if (diff < 60) return `há ${diff}s`;
        if (diff < 3600) return `há ${Math.floor(diff/60)}min`;
        return `há ${Math.floor(diff/3600)}h`;
    } catch(e) { return "ativo"; }
}

function alternarTemaVisual() { document.body.classList.toggle('dark-mode'); }

function navegarAbas(page, btn) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');
    if(btn) btn.classList.add('active');
    
    const titles = { 'home': 'Visão Operacional', 'emprestimos': 'Registrar Novo Empréstimo Ativo', 'bi': 'Análise de Demanda Estatística', 'turmas': 'Gerenciamento de Turmas' };
    document.getElementById('topbar-title').innerText = titles[page];
}

function enviarMensagemToast(msg, tipo) {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div'); t.className = `toast ${tipo}`; t.innerText = msg;
    c.appendChild(t); setTimeout(() => t.remove(), 3000);
}

function enviarFormularioEmprestimo() {
    const notebook = document.getElementById('form-notebook').value.trim();
    const aluno = document.getElementById('form-aluno').value.trim();
    const sala = document.getElementById('form-sala').value.trim();
    const local = document.getElementById('form-local').value.trim();

    if(!notebook || !aluno) { enviarMensagemToast("Preencha os dados obrigatórios.", "error"); return; }

    fetch('/api/emprestimo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notebook, aluno, sala_aluno: sala, local_notebook: local })
    }).then(res => res.json()).then(() => {
        enviarMensagemToast("Empréstimo gravado!", "success");
        document.getElementById('form-notebook').value = '';
        document.getElementById('form-aluno').value = '';
        navegarAbas('home', document.querySelector('.nav-item'));
        sincronizarNucleoDashboard();
    });
}

function abrirModalEdicao(id) {
    const e = cacheEmprestimos.find(x => x.id === id);
    if(!e) return;
    document.getElementById('edit-id').value = e.id;
    document.getElementById('edit-notebook').value = e.notebook;
    document.getElementById('edit-aluno').value = e.aluno;
    document.getElementById('edit-sala').value = e.sala_aluno || '';
    document.getElementById('edit-local').value = e.local_notebook || '';
    document.getElementById('modal-edicao').classList.add('open');
}

function fecharModalEdicao() { document.getElementById('modal-edicao').classList.remove('open'); }

function salvarAlteracaoCadastral() {
    const id = document.getElementById('edit-id').value;
    fetch(`/api/emprestimo/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            notebook: document.getElementById('edit-notebook').value,
            aluno: document.getElementById('edit-aluno').value,
            sala_aluno: document.getElementById('edit-sala').value,
            local_notebook: document.getElementById('edit-local').value
        })
    }).then(() => { fecharModalEdicao(); enviarMensagemToast("Registro alterado!", "success"); sincronizarNucleoDashboard(); });
}

function removerRegistroEmprestimo(id) {
    if(confirm("Deseja expurgar permanentemente esta movimentação?")) {
        fetch(`/api/emprestimo/${id}`, { method: 'DELETE' }).then(() => { enviarMensagemToast("Removido com sucesso.", "success"); sincronizarNucleoDashboard(); });
    }
}

function limparRegistrosAuditoria() {
    if(confirm("Zerar logs automáticos da tela?")) fetch('/api/logs', { method: 'DELETE' }).then(() => sincronizarNucleoDashboard());
}

const arquivo = document.getElementById("arquivo");
const nomeArquivo = document.getElementById("nomeArquivo");
const form = document.getElementById("uploadForm");

// Mostrar nome do arquivo ao selecionar
arquivo.addEventListener("change", () => {

    if (arquivo.files.length > 0) {
        nomeArquivo.textContent =
            arquivo.files[0].name;
    } else {
        nomeArquivo.textContent =
            "Nenhum arquivo selecionado";
    }

});


// Enviar formulário
form.addEventListener("submit", async (e) => {

    e.preventDefault();

    if (!arquivo.files[0]) {
        alert("Selecione um arquivo");
        return;
    }

    const formData = new FormData();

    formData.append(
        "excel",
        arquivo.files[0]
    );

    try {

        const resposta =
        await fetch("/api/importar", {
            method: "POST",
            body: formData
        });

        const dados =
        await resposta.json();

        alert(dados.mensagem);

    } catch (err) {

        console.error(err);

        alert("Erro ao enviar");

    }

});

async function carregarTurmas() {

    const resposta = await fetch("/api/turmas");

    const dados = await resposta.json();

    const tabela = document.getElementById("tabela-turmas-corpo");

    tabela.innerHTML = "";

    dados.forEach(item => {

        const linha = document.createElement("tr");

        linha.innerHTML = `
            <td>${item.turma}</td>
            <td>${item.quantidade}</td>
        `;

        tabela.appendChild(linha);

    });

}

carregarTurmas();

async function carregarTurmasEmprestimo() {

    const resposta = await fetch("/api/buscar-turmas");

    const turmas = await resposta.json();

    const select = document.getElementById("turma");

    turmas.forEach(item => {

        select.innerHTML += `
            <option value="${item.turma}">
                ${item.turma}
            </option>
        `;

    });

}


document.getElementById("turma").addEventListener("change", async function(){

    const turma = this.value;

    const selectAluno =
        document.getElementById("aluno");

    selectAluno.innerHTML =
        `<option>Carregando...</option>`;

    if(!turma){
        selectAluno.innerHTML =
            `<option>Selecione um aluno</option>`;
        return;
    }

    const resposta =
        await fetch(`/api/buscar-alunos/${turma}`);

    const alunos =
        await resposta.json();

    selectAluno.innerHTML =
        `<option value="">Selecione um aluno</option>`;

    alunos.forEach(aluno => {

        selectAluno.innerHTML += `
            <option value="${aluno.id_aluno}">
                ${aluno.nome_aluno}
            </option>
        `;

    });

});


carregarTurmasEmprestimo();