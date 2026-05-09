const pages = document.querySelectorAll('.page');
document.querySelectorAll('nav button').forEach((button) => {
  button.addEventListener('click', () => {
    pages.forEach((page) => page.classList.toggle('active', page.id === button.dataset.page));
  });
});

async function loadSample() {
  const response = await fetch('sample_response.json');
  const model = await response.json();
  document.querySelector('#baseline-sql-panel pre').textContent = model.baseline_sql_panel.sql || '(none)';
  document.querySelector('#system-sql-panel pre').textContent = model.system_sql_panel.sql || '(none)';
  document.querySelector('#difference-summary-panel ul').innerHTML = model.difference_summary_panel.items.map((item) => `<li>${item.category}: ${item.message}</li>`).join('');
  document.querySelector('#applied-definitions-panel pre').textContent = JSON.stringify(model.applied_definitions_panel, null, 2);
  document.querySelector('#comment-mode-comparison-panel pre').textContent = JSON.stringify(model.comment_mode_comparison_panel, null, 2);
  document.querySelector('#verification-panel pre').textContent = JSON.stringify(model.verification_panel, null, 2);
  document.querySelector('#failure-state-panel pre').textContent = JSON.stringify(model.failure_state_panel, null, 2);
  document.querySelector('#preview-result-panel pre').textContent = JSON.stringify(model.preview_result_panel, null, 2);
  document.querySelector('#suggested-actions-panel ul').innerHTML = model.suggested_actions_panel.actions.map((action) => `<li>${action}</li>`).join('');
}

document.querySelector('#load-sample').addEventListener('click', loadSample);
loadSample();
