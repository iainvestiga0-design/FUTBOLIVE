const dialog = document.getElementById('infoDialog');
const title = document.getElementById('dialogTitle');
const text = document.getElementById('dialogText');
function showInfo(t, m){ title.textContent=t; text.textContent=m; dialog.showModal(); }
document.getElementById('loginBtn').addEventListener('click',()=>showInfo('Acceso de usuarios','El registro y el inicio de sesión se implementarán en la siguiente etapa. Todavía no se crean cuentas.'));
document.getElementById('notifyBtn').addEventListener('click',()=>showInfo('FUTBOLIVE Premium','Estamos preparando esta sección. En esta versión no se realizan cobros ni se activa ninguna suscripción.'));
document.getElementById('closeDialog').addEventListener('click',()=>dialog.close());
document.getElementById('okDialog').addEventListener('click',()=>dialog.close());
document.getElementById('menuToggle').addEventListener('click',()=>document.getElementById('mobileNav').classList.toggle('open'));
document.querySelectorAll('.mobile-nav a').forEach(a=>a.addEventListener('click',()=>document.getElementById('mobileNav').classList.remove('open')));
document.querySelectorAll('.filter').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('.filter').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.match-card').forEach(card=>{
    card.hidden = btn.dataset.filter!=='todos' && card.dataset.region!==btn.dataset.filter;
  });
}));
