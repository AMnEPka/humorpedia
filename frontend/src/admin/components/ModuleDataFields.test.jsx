import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import ModuleDataFields from './ModuleDataFields';

let container;
let root;
let saved;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  saved = null;
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function mount(type, initial = {}) {
  function Harness() {
    const [data, setData] = useState(initial);
    return <form onSubmit={event => { event.preventDefault(); saved = { id: 'existing', type, visible: true, order: 4, data }; }}>
      <ModuleDataFields type={type} data={data} onChange={setData} />
      <button type="submit">Сохранить модуль</button>
    </form>;
  }
  act(() => root.render(<Harness />));
}
function button(text) {
  const target = [...container.querySelectorAll('button')].find(button => button.textContent === text || button.getAttribute('aria-label') === text);
  expect(target).toBeDefined();
  act(() => target.click());
}
function field(label, value, index = 0) {
  const targetLabel = [...container.querySelectorAll('label')].filter(item => item.textContent === label)[index];
  expect(targetLabel).toBeDefined();
  const input = document.getElementById(targetLabel.htmlFor);
  act(() => {
    const prototype = input.tagName === 'SELECT' ? HTMLSelectElement.prototype : input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event(input.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  });
}

it.each([
  ['tv_appearances', 'Эфир', 'Шоу', 'items', 'show'],
  ['games_list', 'Игра', 'Соперник', 'games', 'opponent'],
  ['episodes_list', 'Выпуск', 'Название выпуска', 'episodes', 'title'],
  ['quiz_results', 'Результат', 'Название результата', 'results', 'title'],
  ['related_links', 'Ссылка', 'Название', 'links', 'title'],
  ['cast_list', 'Участник', 'Имя', 'cast', 'name'],
  ['seasons_list', 'Сезон', 'Название', 'seasons', 'title'],
])('%s: добавляет, изменяет, удаляет записи и сохраняет остальные данные', (type, itemLabel, fieldLabel, key, name) => {
  mount(type, { imported: 'keep', [key]: [{ [name]: 'Исходный', legacy_id: 51 }] });
  field(fieldLabel, 'Исправленный');
  button(`Добавить: ${itemLabel}`);
  field(fieldLabel, 'Новый', 1);
  button('Сохранить модуль');
  expect(saved).toMatchObject({ id: 'existing', type, visible: true, order: 4,
    data: { imported: 'keep', [key]: [{ [name]: 'Исправленный', legacy_id: 51 }, { [name]: 'Новый' }] },
  });
  button(`Удалить: ${itemLabel} 1`);
  button('Сохранить модуль');
  expect(saved.data[key]).toHaveLength(1);
  expect(saved.data[key][0][name]).toBe('Новый');
});

it('теги сохраняются строками после добавления, правки и удаления', () => {
  mount('tags', { tags: ['КВН'], imported: 1 });
  field('Название тега', 'Юмор');
  button('Добавить: Тег');
  field('Название тега', 'Шоу', 1);
  button('Удалить: Тег 1');
  button('Сохранить модуль');
  expect(saved.data).toEqual({ tags: ['Шоу'], imported: 1 });
});

it('номер выпуска сохраняет числом, а список гостей массивом без потери других полей', () => {
  mount('episodes_list');
  button('Добавить: Выпуск');
  field('Сезон', '2');
  field('Номер выпуска', '7');
  field('Гости (по одному на строке)', 'Анна\nБорис');
  field('Ссылка на видео', 'https://example.test/video');
  button('Сохранить модуль');
  expect(saved.data.episodes[0]).toMatchObject({ season: 2, episode: 7, guests: ['Анна', 'Борис'], video_url: 'https://example.test/video' });
});

it('вопросы поддерживают одиночный, множественный и текстовый ответ, пояснения и удаление', () => {
  mount('quiz_questions', { preserved: true });
  button('Добавить: Вопрос');
  field('Текст вопроса', 'Кто победил?');
  field('Текст ответа', 'Команда А');
  button('Добавить: Вариант ответа');
  field('Текст ответа', 'Команда Б', 1);
  act(() => container.querySelectorAll('input[type="radio"]')[0].click());
  act(() => container.querySelectorAll('input[type="radio"]')[1].click());
  button('Сохранить модуль');
  expect(saved.data.questions[0].options.map(option => option.correct)).toEqual([false, true]);
  field('Тип вопроса', 'multiple');
  act(() => container.querySelectorAll('input[type="checkbox"]')[0].click());
  button('Сохранить модуль');
  expect(saved.data.questions[0].options.map(option => option.correct)).toEqual([true, true]);
  field('Тип вопроса', 'single');
  button('Сохранить модуль');
  expect(saved.data.questions[0].options.filter(option => option.correct)).toHaveLength(1);
  button('Удалить: Вариант ответа 2');
  field('Тип вопроса', 'text');
  field('Правильный ответ', 'Команда А');
  field('Пояснение правильного ответа', 'Верно!');
  button('Сохранить модуль');
  expect(saved.data).toMatchObject({ preserved: true, questions: [{ type: 'text', question: 'Кто победил?', correct_answer: 'Команда А', success_explanation: 'Верно!' }] });
  button('Удалить: Вопрос 1');
  button('Сохранить модуль');
  expect(saved.data.questions).toEqual([]);
});

it.each(['best_articles', 'interesting'])('%s: записывает заголовок и ограничивает количество', type => {
  mount(type);
  field('Заголовок блока', 'Читайте также');
  field('Количество статей', '55');
  button('Сохранить модуль');
  expect(saved.data).toEqual({ title: 'Читайте также', limit: 20 });
});

it('случайная страница записывает выбранный тип', () => {
  mount('random_page', { title: 'Открыть' });
  field('Тип случайной страницы', 'city');
  button('Сохранить модуль');
  expect(saved.data).toEqual({ title: 'Открыть', content_type: 'city' });
});

it('изображение сохраняет URL, подпись и alt', () => {
  mount('image');
  field('URL изображения', '/media/photo.jpg');
  field('Подпись', 'Финал');
  field('Описание изображения (alt)', 'Команда на сцене');
  button('Сохранить модуль');
  expect(saved.data).toEqual({ url: '/media/photo.jpg', caption: 'Финал', alt: 'Команда на сцене' });
});

it('неизвестный тип показывает причину и сохраняет данные без JSON-редактора', () => {
  mount('future_module', { unknown: ['preserved'] });
  expect(container.querySelector('[role="status"]').textContent).toContain('нет формы');
  expect(container.querySelector('textarea')).toBeNull();
  button('Сохранить модуль');
  expect(saved.data).toEqual({ unknown: ['preserved'] });
});

it('старый текст редактирует отображаемый content_html, включая полную очистку', () => {
  mount('text', { content_html: '<p>Видимый текст</p>', content: 'Старый текст', legacy: true });
  field('Текст', '');
  button('Сохранить модуль');
  expect(saved.data).toEqual({ content_html: '', content: '', legacy: true });
});
