import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, CheckCircle2, Phone } from 'lucide-react';

const steps = [
  { id: 'city', question: 'В каком городе ваш объект?', type: 'text', placeholder: 'Например: Москва' },
  { id: 'type', question: 'Тип недвижимости', type: 'choice', options: ['Квартира', 'Коммерция', 'ИЖС'] },
  { id: 'details', question: 'Что планируете изменить?', type: 'textarea', placeholder: 'Например: перенос кухни или снос стены' },
  { id: 'phone', question: 'Ваш номер телефона', type: 'tel', placeholder: '+7 (___) ___-__-__' }
];

function QuizView() {
  const [step, setStep] = useState(0);
  const [formData, setFormData] = useState({});
  const [isFinished, setIsFinished] = useState(false);

  const handleNext = (value) => {
    const newData = { ...formData, [steps[step].id]: value };
    setFormData(newData);

    if (step < steps.length - 1) {
      setStep(step + 1);
    } else {
      submitQuiz(newData);
    }
  };

  const submitQuiz = async (data) => {
    console.log('Submitting:', data);
    // Имитация отправки
    setIsFinished(true);
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
    }
  };

  if (isFinished) {
    return (
      <div className="p-6 text-center animate-in fade-in zoom-in duration-500">
        <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <CheckCircle2 size={40} className="text-terion-green" />
        </div>
        <h2 className="text-2xl font-bold mb-4 text-terion-black">Заявка принята!</h2>
        <p className="text-gray-600 mb-8">Эксперт ТЕРИОН изучит ваши данные и свяжется с вами в течение 30 минут.</p>
        <button className="tg-button w-full flex items-center justify-center gap-2">
          <Phone size={20} /> Позвонить сейчас
        </button>
      </div>
    );
  }

  const current = steps[step];

  return (
    <div className="p-6">
      <div className="mb-8 flex gap-2">
        {steps.map((_, i) => (
          <div key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${i <= step ? 'bg-terion-green' : 'bg-gray-200'}`} />
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ x: 20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -20, opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          <h2 className="text-2xl font-bold mb-8 text-terion-black leading-tight">{current.question}</h2>

          {current.type === 'choice' ? (
            <div className="grid gap-3">
              {current.options.map(opt => (
                <button
                  key={opt}
                  onClick={() => handleNext(opt)}
                  className="w-full text-left p-4 rounded-xl border-2 border-gray-100 hover:border-terion-green hover:bg-green-50 transition-all font-medium flex justify-between items-center group"
                >
                  {opt}
                  <ChevronRight size={20} className="text-gray-300 group-hover:text-terion-green" />
                </button>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {current.type === 'textarea' ? (
                <textarea
                  className="w-full p-4 rounded-xl border-2 border-gray-100 focus:border-terion-green focus:bg-white bg-gray-50 outline-none min-h-[120px]"
                  placeholder={current.placeholder}
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && e.shiftKey === false && handleNext(e.target.value)}
                />
              ) : (
                <input
                  type={current.type}
                  className="w-full p-4 rounded-xl border-2 border-gray-100 focus:border-terion-green focus:bg-white bg-gray-50 outline-none"
                  placeholder={current.placeholder}
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleNext(e.target.value)}
                />
              )}
              <button
                onClick={(e) => {
                  const input = e.currentTarget.previousSibling;
                  if (input.value) handleNext(input.value);
                }}
                className="tg-button w-full"
              >
                Продолжить
              </button>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

export default QuizView;
