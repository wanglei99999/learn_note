import { TOPICS } from './content.js';

document.getElementById('contents').innerHTML = `<a href="#example">示例：读文件并总结</a>${TOPICS.map(topic => `<a href="#${topic.id}">${topic.title}</a>`).join('')}<a href="#glossary">术语速查</a>`;
document.getElementById('topics').innerHTML = TOPICS.map((topic, i) => `<section id="${topic.id}"><span class="eyebrow">${String(i + 1).padStart(2, '0')} / SOURCE NOTES</span><h2>${topic.title}</h2><p class="lead">${topic.lead}</p>${topic.html}</section>`).join('');
if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
