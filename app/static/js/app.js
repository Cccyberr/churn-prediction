// Mark-as-taken handler for recommendation cards
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.log-action-btn');
  if (!btn) return;
  const customerId = btn.dataset.customerId;
  if (!customerId) { alert('Missing customer id'); return; }

  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    const r = await fetch('/api/retention-action', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        customer_id: customerId,
        action_type: btn.dataset.actionType,
        action_detail: btn.dataset.actionDetail,
        cost_estimate: parseFloat(btn.dataset.cost || '0'),
        outcome: 'pending',
      }),
    });
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    btn.textContent = '✓ Logged';
    btn.style.borderColor = 'var(--risk-low)';
    btn.style.color = 'var(--risk-low)';
  } catch (err) {
    btn.disabled = false;
    btn.textContent = original;
    alert('Failed to log action: ' + err.message);
  }
});
