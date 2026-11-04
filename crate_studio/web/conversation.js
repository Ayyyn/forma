export function conversationUI({$,esc,state,api,openProposal}) {
  let epoch=0;
  async function refresh() {
    const version=++epoch, id=state.snapshot?.id;
    if(!id)return;
    try {
      const result=await api('/conversation/'+encodeURIComponent(id));
      if(version!==epoch||state.snapshot?.id!==id)return;
      $('#agent-history').innerHTML=result.messages.filter(m=>!(m.role==='assistant'&&m.run_id===state.agentJob&&!$('#agent-result').classList.contains('hidden'))).map(m=>`<article class="chat-message ${m.role}"><small>${m.role==='user'?'You':'Muse'}${m.status==='error'?' · request failed':''}</small><div>${esc(m.text)}</div>${m.questions?.length?`<div class="chat-questions">${m.questions.map(q=>`<p>${esc(q)}</p>`).join('')}</div>`:''}${m.role==='assistant'&&m.status==='ready'&&m.document_id===id?`<button data-reopen-proposal="${esc(m.run_id)}">Review proposal</button>`:''}</article>`).join('');
      $('#agent-history').querySelectorAll('[data-reopen-proposal]').forEach(button=>button.onclick=()=>openProposal(button.dataset.reopenProposal,result.messages.find(m=>m.role==='user'&&m.run_id===button.dataset.reopenProposal)?.text||''));
      $('#agent-history').scrollTop=$('#agent-history').scrollHeight;
      $('#chat-storage').textContent='Saved on this computer';
    }catch(error){if(version===epoch)$('#chat-storage').textContent='History unavailable: '+error.message;}
  }
  $('#chat-expand').onclick=()=>{
    const expanded=$('.agent-panel').classList.toggle('chat-expanded');
    $('#chat-expand').textContent=expanded?'Collapse chat':'Expand chat';
  };
  return {refresh};
}
