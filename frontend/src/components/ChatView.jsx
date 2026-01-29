import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot } from 'lucide-react';

function ChatView() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Здравствуйте! Я Антон, ИИ-консультант ТЕРИОН. Готов ответить на любые вопросы по согласованию перепланировки.' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setIsLoading(true);

    try {
      // Здесь будет запрос к нашему API
      setTimeout(() => {
        setMessages(prev => [...prev, { role: 'assistant', text: 'Каждый проект уникален. Для точного ответа мне нужно изучить ваши документы. Хотите оставить заявку на бесплатный анализ?' }]);
        setIsLoading(false);
      }, 1500);
    } catch (err) {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)]">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] p-3 rounded-2xl flex gap-3 ${
              m.role === 'user' ? 'bg-terion-green text-white rounded-tr-none' : 'bg-white border text-terion-black rounded-tl-none shadow-sm'
            }`}>
              {m.role === 'assistant' && <Bot size={18} className="shrink-0 mt-1" />}
              <div className="text-[15px] leading-relaxed">{m.text}</div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border p-3 rounded-2xl rounded-tl-none flex gap-2 items-center">
              <div className="w-1.5 h-1.5 bg-terion-green rounded-full animate-bounce" />
              <div className="w-1.5 h-1.5 bg-terion-green rounded-full animate-bounce delay-75" />
              <div className="w-1.5 h-1.5 bg-terion-green rounded-full animate-bounce delay-150" />
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      <div className="p-4 bg-white border-t sticky bottom-0">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Задайте вопрос Антону..."
            className="flex-1 p-3 bg-gray-50 rounded-xl outline-none focus:bg-white border focus:border-terion-green transition-all"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="w-12 h-12 bg-terion-green text-white rounded-xl flex items-center justify-center disabled:opacity-50 active:scale-95 transition-all"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatView;
