/** @jest-environment node */

import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { getQuizModuleData, QuizAdditionalModules } from './QuizDetailPage';
import { updateQuizModules } from '../../admin/pages/QuizEditPage';

jest.mock('../utils/api', () => ({ __esModule: true, default: {}, publicApi: {} }));
jest.mock('../../admin/utils/api', () => ({ contentApi: {} }));
jest.mock('../../admin/components/ModuleEditor', () => () => null);
jest.mock('../../admin/components/TagSelector', () => () => null);

test('saving quiz questions preserves additional blocks and special module metadata', () => {
  const extra = { id: 'intro', type: 'text_block', order: 5, visible: true, data: { content: '<b>Вступление</b>' } };
  const questionModule = {
    id: 'legacy-questions', type: 'quiz_questions', order: 7, title: 'Вопросы', visible: false,
    data: { questions: [{ question: 'Старый вопрос' }], custom_field: 'preserve' },
  };
  const resultModule = {
    id: 'legacy-results', type: 'quiz_results', order: 9, visible: false, data: { results: [] },
  };
  const original = [extra, questionModule, resultModule];
  const questions = [{ question: 'Новый вопрос', options: [{ text: 'Да', correct: true }] }];
  const results = [{ min_score: 0, max_score: 1, title: 'Результат' }];
  const saved = updateQuizModules(original, questions, results);

  expect(saved).toEqual([
    extra,
    { ...questionModule, data: { ...questionModule.data, questions } },
    { ...resultModule, data: { results } },
  ]);
  expect(original[1].data.questions[0].question).toBe('Старый вопрос');
  expect(saved[0]).toBe(extra);
});

test('saving a new quiz creates the two required specialized modules', () => {
  const saved = updateQuizModules([], [], []);
  expect(saved.map(module => module.type)).toEqual(['quiz_questions', 'quiz_results']);
  expect(saved.every(module => module.visible === true)).toBe(true);
});

test('quiz gameplay ignores explicitly hidden questions and result modules', () => {
  const hidden = [
    { type: 'quiz_questions', visible: false, data: { questions: [{ question: 'Скрытый вопрос' }] } },
    { type: 'quiz_results', visible: false, data: { results: [{ title: 'Скрытый результат' }] } },
  ];
  expect(getQuizModuleData(hidden)).toEqual({ questions: [], results: [] });
  const questions = [{ question: 'Видимый вопрос' }];
  const results = [{ title: 'Видимый результат' }];
  expect(getQuizModuleData([
    ...hidden,
    { type: 'quiz_questions', data: { questions } },
    { type: 'quiz_results', data: { results } },
  ])).toEqual({ questions, results });
});

test('the quiz start screen renders visible extra modules in order without gameplay payloads', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <QuizAdditionalModules modules={[
        { id: 'later', type: 'quote', order: 2, data: { text: 'Вторая цитата' } },
        { id: 'q', type: 'quiz_questions', data: { questions: [], content: 'Внутренние вопросы' } },
        { id: 'r', type: 'quiz_results', data: { results: [], content: 'Внутренние результаты' } },
        { id: 'hidden', type: 'text_block', visible: false, data: { content: 'Скрытый блок' } },
        { id: 'first', type: 'text_block', order: 1, data: { content: '<b>Первый блок</b>' } },
      ]} />
    </MemoryRouter>
  );
  expect(html).toContain('<b>Первый блок</b>');
  expect(html).toContain('Вторая цитата');
  expect(html.indexOf('Первый блок')).toBeLessThan(html.indexOf('Вторая цитата'));
  expect(html).not.toContain('Внутренние вопросы');
  expect(html).not.toContain('Внутренние результаты');
  expect(html).not.toContain('Скрытый блок');
});
