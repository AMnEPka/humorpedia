import { useId } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

// All changes preserve fields not owned by the form, including imported metadata.
function Field({ label, value, onChange, type = 'text', options, min, max }) {
  const id = useId();
  const props = { id, value: value ?? '', onChange: event => onChange(
    type === 'number' ? (event.target.value === '' ? '' : Number(event.target.value)) : event.target.value
  ) };
  return <div className="space-y-1">
    <label htmlFor={id} className="text-sm font-medium">{label}</label>
    {options ? <select {...props} className="flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm">
      {options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}
    </select> : type === 'textarea' ? <Textarea {...props} rows={3} /> : <Input {...props} type={type} min={min} max={max} />}
  </div>;
}

function Rows({ label, items, onChange, create, children }) {
  return <div className="space-y-3">
    {items.map((item, index) => <fieldset key={index} className="border rounded-lg p-3 space-y-3">
      <legend className="px-1 text-sm font-medium">{label} {index + 1}</legend>
      {children(item, patch => onChange(items.map((entry, i) => i === index ? { ...entry, ...patch } : entry)), index)}
      <Button type="button" variant="outline" size="sm" aria-label={`Удалить: ${label} ${index + 1}`}
        onClick={() => onChange(items.filter((_, i) => i !== index))}>Удалить</Button>
    </fieldset>)}
    <Button type="button" variant="outline" onClick={() => onChange([...items, create()])}>Добавить: {label}</Button>
  </div>;
}

const records = {
  tv_appearances: { key: 'items', label: 'Эфир', fields: [['show', 'Шоу'], ['date', 'Дата'], ['description', 'Описание', 'textarea'], ['video_url', 'Ссылка на видео']] },
  games_list: { key: 'games', label: 'Игра', fields: [['date', 'Дата'], ['opponent', 'Соперник'], ['league', 'Лига'], ['result', 'Результат'], ['video_url', 'Ссылка на видео']] },
  episodes_list: { key: 'episodes', label: 'Выпуск', fields: [['season', 'Сезон', 'number'], ['episode', 'Номер выпуска', 'number'], ['title', 'Название выпуска'], ['air_date', 'Дата эфира'], ['guests', 'Гости (по одному на строке)', 'lines'], ['video_url', 'Ссылка на видео'], ['description', 'Описание', 'textarea']] },
  related_links: { key: 'links', label: 'Ссылка', fields: [['title', 'Название'], ['url', 'Адрес ссылки']] },
  cast_list: { key: 'cast', label: 'Участник', fields: [['name', 'Имя'], ['role', 'Роль'], ['slug', 'Страница человека (slug)'], ['photo', 'Фото (URL)']] },
  seasons_list: { key: 'seasons', label: 'Сезон', fields: [['title', 'Название'], ['year', 'Год', 'number'], ['episodes_count', 'Количество серий', 'number']] },
  quiz_results: { key: 'results', label: 'Результат', fields: [['min_score', 'Минимум баллов', 'number'], ['max_score', 'Максимум баллов', 'number'], ['title', 'Название результата'], ['description', 'Описание', 'textarea'], ['image', 'Изображение (URL)']] },
};

const lines = value => Array.isArray(value) ? value.join('\n') : value || '';
const splitLines = value => value.split('\n');
const newId = () => `item-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

function Questions({ data, onChange }) {
  const questions = data.questions || [];
  return <Rows label="Вопрос" items={questions} onChange={next => onChange({ ...data, questions: next })}
    create={() => ({ id: newId(), type: 'single', question: '', options: [{ id: newId(), text: '', correct: false }] })}>
    {(question, update, index) => <>
      <Field label="Текст вопроса" value={question.question} onChange={question => update({ question })} type="textarea" />
      <Field label="Тип вопроса" value={question.type || 'single'} options={[
        ['single', 'Один правильный ответ'], ['multiple', 'Несколько правильных ответов'], ['text', 'Текстовый ответ'],
      ]} onChange={type => update({ type, ...(type === 'text' ? { correct_answer: question.correct_answer || '' } : {
        options: question.options?.length ? question.options.map((option, i) => ({ ...option,
          correct: type === 'single' ? i === question.options.findIndex(entry => entry.correct) : option.correct,
        })) : [{ id: newId(), text: '', correct: false }],
      }) })} />
      <Field label="Изображение вопроса (URL)" value={question.image} onChange={image => update({ image })} />
      {question.type === 'text' ? <Field label="Правильный ответ" value={question.correct_answer} onChange={correct_answer => update({ correct_answer })} /> :
        <Rows label="Вариант ответа" items={question.options || []} onChange={options => update({ options })}
          create={() => ({ id: newId(), text: '', correct: false })}>
          {(option, updateOption, optionIndex) => <>
            <Field label="Текст ответа" value={option.text} onChange={text => updateOption({ text })} />
            <label className="flex gap-2 items-center text-sm">
              <input type={question.type === 'multiple' ? 'checkbox' : 'radio'} name={`correct-${index}`}
                checked={Boolean(option.correct)} onChange={event => update({ options: question.options.map((entry, i) => ({
                  ...entry, correct: i === optionIndex ? event.target.checked : question.type === 'multiple' ? entry.correct : false,
                })) })} /> Правильный ответ
            </label>
          </>}
        </Rows>}
      <Field label="Общее пояснение" value={question.explanation} type="textarea" onChange={explanation => update({ explanation })} />
      <Field label="Пояснение правильного ответа" value={question.success_explanation} type="textarea" onChange={success_explanation => update({ success_explanation })} />
      <Field label="Пояснение ошибки" value={question.error_explanation} type="textarea" onChange={error_explanation => update({ error_explanation })} />
    </>}
  </Rows>;
}

export default function ModuleDataFields({ type, data = {}, onChange }) {
  const update = patch => onChange({ ...data, ...patch });
  const title = <Field label="Заголовок блока" value={data.title} onChange={title => update({ title })} />;
  if (records[type]) {
    const { key, label, fields } = records[type];
    const items = data[key] || (type === 'tv_appearances' ? data.appearances : []) || [];
    return <div className="space-y-4">{title}<Rows label={label} items={items}
      onChange={items => update({ [key]: items })}
      create={() => Object.fromEntries(fields.map(([key, , type]) => [key, type === 'lines' ? [] : type === 'number' ? 0 : '']))}>
      {(item, change) => fields.map(([key, label, type]) => <Field key={key} label={label}
        type={type === 'lines' ? 'textarea' : type} value={type === 'lines' ? lines(item[key]) : item[key]}
        min={type === 'number' ? 0 : undefined}
        onChange={value => change({ [key]: type === 'lines' ? splitLines(value) : value })} />)}
    </Rows></div>;
  }
  switch (type) {
    case 'quiz_questions': return <Questions data={data} onChange={onChange} />;
    case 'tags': return <div className="space-y-4">{title}
      <Rows label="Тег" items={(data.tags || []).map(tag => ({ tag }))} create={() => ({ tag: '' })}
        onChange={items => update({ tags: items.map(item => item.tag) })}>
        {(item, change) => <Field label="Название тега" value={item.tag} onChange={tag => change({ tag })} />}
      </Rows>
    </div>;
    case 'image': return <div className="space-y-4">
      <Field label="URL изображения" value={data.url} onChange={url => update({ url })} />
      <Field label="Подпись" value={data.caption} onChange={caption => update({ caption })} />
      <Field label="Описание изображения (alt)" value={data.alt} onChange={alt => update({ alt })} />
    </div>;
    case 'best_articles':
    case 'interesting': return <div className="space-y-4">{title}
      <Field label="Количество статей" type="number" min={1} max={20} value={data.limit ?? 3}
        onChange={limit => update({ limit: limit === '' ? '' : Math.max(1, Math.min(20, limit)) })} />
      <p className="text-sm text-muted-foreground">{type === 'best_articles' ? 'Доступные статьи с высоким рейтингом, кроме архивных.' : 'Доступные статьи с отметкой «Избранное», кроме архивных.'}</p>
    </div>;
    case 'random_page': return <div className="space-y-4">{title}
      <Field label="Тип случайной страницы" value={data.content_type || 'article'} onChange={content_type => update({ content_type })}
        options={Object.entries({ person: 'Человек', team: 'Команда', show: 'Шоу', article: 'Статья', news: 'Новость', quiz: 'Квиз', city: 'Город' })} />
    </div>;
    case 'humor_chronicles': return <div className="space-y-4">{title}
      <p className="text-sm text-muted-foreground">Новости, статьи и шоу, связанные с человеком, загружаются автоматически.</p>
    </div>;
    case 'person_card': return <div className="space-y-4">
      {[['name', 'Имя'], ['photo', 'Фото (URL)'], ['role', 'Роль'], ['description', 'Описание']].map(([key, label]) =>
        <Field key={key} label={label} value={data[key]} onChange={value => update({ [key]: value })} />)}
    </div>;
    case 'html':
    case 'text': return <div className="space-y-4">{title}
      <Field label={type === 'html' ? 'HTML содержимое' : 'Текст'} type="textarea" value={type === 'text' && data.content_html ? data.content_html : data.content}
        onChange={content => update(type === 'text' && data.content_html !== undefined ? { content_html: content, content } : { content })} />
    </div>;
    case 'divider': return <p className="text-sm text-muted-foreground">Горизонтальный разделитель. Дополнительных настроек нет.</p>;
    default: return <p role="status" className="text-sm text-muted-foreground">Для типа «{type}» нет формы редактирования. Имеющиеся данные сохраняются.</p>;
  }
}
