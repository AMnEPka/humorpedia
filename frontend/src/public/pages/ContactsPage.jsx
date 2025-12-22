import { Mail, MapPin, Send } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

export default function ContactsPage() {
  const handleSubmit = (e) => {
    e.preventDefault();
    // Handle form submission
    alert('Спасибо за сообщение! Мы свяжемся с вами в ближайшее время.');
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <ol className="flex items-center gap-2 text-sm text-gray-500">
          <li><Link to="/" className="hover:text-blue-600">Главная</Link></li>
          <li>/</li>
          <li className="text-gray-900">Контакты</li>
        </ol>
      </nav>

      <h1 className="text-3xl font-bold text-gray-900 mb-8">Контакты</h1>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Contact Info */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Свяжитесь с нами</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-start gap-3">
                <Mail className="h-5 w-5 text-blue-600 mt-0.5" />
                <div>
                  <div className="font-medium">Электронная почта</div>
                  <a href="mailto:info@humorpedia.ru" className="text-blue-600 hover:underline">
                    info@humorpedia.ru
                  </a>
                </div>
              </div>
              
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-blue-600 mt-0.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.744c-.66 0-.862-.523-2.049-1.713-1.033-1.001-1.49-1.135-1.744-1.135-.356 0-.458.102-.458.593v1.575c0 .424-.135.678-1.253.678-1.846 0-3.896-1.118-5.335-3.202C4.624 10.857 4 8.684 4 8.245c0-.254.102-.491.593-.491h1.744c.44 0 .61.203.78.677.863 2.49 2.303 4.675 2.896 4.675.22 0 .322-.102.322-.66V9.721c-.068-1.186-.695-1.287-.695-1.71 0-.204.17-.407.44-.407h2.744c.373 0 .508.203.508.643v3.473c0 .372.17.508.271.508.22 0 .407-.136.813-.542 1.254-1.406 2.151-3.574 2.151-3.574.119-.254.322-.491.763-.491h1.744c.525 0 .644.27.525.643-.22 1.017-2.354 4.031-2.354 4.031-.186.305-.254.44 0 .78.186.254.796.779 1.203 1.253.745.847 1.32 1.558 1.473 2.049.17.474-.085.716-.576.716z"/>
                </svg>
                <div>
                  <div className="font-medium">ВКонтакте</div>
                  <a href="https://vk.com/humorpedia" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    vk.com/humorpedia
                  </a>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 text-blue-600 mt-0.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                </svg>
                <div>
                  <div className="font-medium">Telegram</div>
                  <a href="https://t.me/humorpedia" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    t.me/humorpedia
                  </a>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>О проекте</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-600">
                Humorpedia — это энциклопедия юмора, посвящённая миру КВН, комедийным шоу и людям, 
                которые дарят нам смех. Мы собираем информацию о командах, участниках, 
                истории и достижениях юмористического движения России и СНГ.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Contact Form */}
        <Card>
          <CardHeader>
            <CardTitle>Напишите нам</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Ваше имя</Label>
                <Input id="name" placeholder="Иван Иванов" required />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" placeholder="ivan@example.com" required />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="subject">Тема</Label>
                <Input id="subject" placeholder="Тема сообщения" required />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="message">Сообщение</Label>
                <Textarea id="message" placeholder="Ваше сообщение..." rows={5} required />
              </div>
              
              <Button type="submit" className="w-full">
                <Send className="mr-2 h-4 w-4" /> Отправить
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
