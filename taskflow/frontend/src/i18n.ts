export type Locale = "en" | "ar";

type Tree = { [key: string]: string | Tree };

export const dictionaries: Record<Locale, { dir: "ltr" | "rtl"; label: string; strings: Tree }> = {
  en: {
    dir: "ltr",
    label: "English",
    strings: {
      eyebrow: "Sample workload",
      title: "TaskFlow",
      subtitle: "Tasks",
      language: "Language",
      skip: "Skip to content",
      status: {
        loading: "API Status: Checking",
        healthy: "API Status: Healthy",
        not_ready: "API Status: Not Ready",
        unavailable: "API Status: Unavailable",
      },
      banner: {
        notReady: "The API process is running, but PostgreSQL is not reachable.",
        unavailable: "The API is unreachable. Start the backend and refresh this page.",
      },
      form: {
        add: "Add Task",
        adding: "Adding…",
        title: "Title",
        description: "Description",
        titlePlaceholder: "Write the on-call handoff notes",
        descriptionPlaceholder: "What needs to happen, and how you will know it is done.",
      },
      list: {
        title: "Tasks",
        count: "{pending} pending · {completed} completed",
        loading: "Loading tasks…",
        empty: "No tasks yet",
        emptyBody: "Add a task when you want TaskFlow to track it.",
        pending: "Pending",
        completed: "Completed",
        created: "Created",
      },
      actions: {
        complete: "Complete",
        delete: "Delete",
        cancel: "Cancel",
        working: "Working…",
      },
      dialog: {
        title: "Delete this task?",
        body: "Delete “{title}”? The task text is kept as you wrote it.",
        confirm: "Delete",
      },
      notice: {
        added: "Task added.",
        completed: "Task completed.",
        deleted: "Task deleted.",
      },
      errors: {
        unreachable: "The API is unreachable.",
        unexpected: "The API returned an unexpected error.",
        rejected: "The request was rejected.",
        load: "Unable to load tasks.",
        add: "Unable to add the task.",
        update: "Unable to update the task.",
        delete: "Unable to delete the task.",
        technical: "Technical detail",
      },
    },
  },
  ar: {
    dir: "rtl",
    label: "العربية",
    strings: {
      eyebrow: "عبء عمل تجريبي",
      title: "TaskFlow",
      subtitle: "المهام",
      language: "اللغة",
      skip: "تخطي إلى المحتوى",
      status: {
        loading: "حالة الواجهة: جارٍ الفحص",
        healthy: "حالة الواجهة: سليمة",
        not_ready: "حالة الواجهة: غير جاهزة",
        unavailable: "حالة الواجهة: غير متاحة",
      },
      banner: {
        notReady: "عملية الواجهة تعمل، لكن PostgreSQL غير قابل للوصول.",
        unavailable: "الواجهة غير قابلة للوصول. شغّل الخدمة الخلفية ثم حدّث الصفحة.",
      },
      form: {
        add: "إضافة مهمة",
        adding: "جارٍ الإضافة…",
        title: "العنوان",
        description: "الوصف",
        titlePlaceholder: "اكتب ملاحظات تسليم المناوبة",
        descriptionPlaceholder: "ما الذي يجب أن يحدث، وكيف تعرف أنه اكتمل.",
      },
      list: {
        title: "المهام",
        count: "{pending} قيد الانتظار · {completed} مكتملة",
        loading: "جارٍ تحميل المهام…",
        empty: "لا توجد مهام حالياً",
        emptyBody: "أضف مهمة عندما تريد أن يتابعها TaskFlow.",
        pending: "قيد الانتظار",
        completed: "مكتملة",
        created: "أُنشئت",
      },
      actions: {
        complete: "إكمال",
        delete: "حذف",
        cancel: "إلغاء",
        working: "جارٍ التنفيذ…",
      },
      dialog: {
        title: "حذف هذه المهمة؟",
        body: "حذف “{title}”؟ يبقى نص المهمة كما كتبته.",
        confirm: "حذف",
      },
      notice: {
        added: "تمت إضافة المهمة.",
        completed: "اكتملت المهمة.",
        deleted: "حُذفت المهمة.",
      },
      errors: {
        unreachable: "الواجهة غير قابلة للوصول.",
        unexpected: "أعادت الواجهة خطأ غير متوقع.",
        rejected: "رُفض الطلب.",
        load: "تعذر تحميل المهام.",
        add: "تعذرت إضافة المهمة.",
        update: "تعذر تحديث المهمة.",
        delete: "تعذر حذف المهمة.",
        technical: "تفصيل تقني",
      },
    },
  },
};

const STORAGE_KEY = "taskflow.lang";

const KNOWN_ERRORS: Record<string, string> = {
  "The API is unreachable.": "errors.unreachable",
  "The API returned an unexpected error.": "errors.unexpected",
  "The request was rejected.": "errors.rejected",
  "Could not load tasks.": "errors.load",
  "Could not add the task.": "errors.add",
  "Could not update the task.": "errors.update",
  "Could not delete the task.": "errors.delete",
};

export function detectLocale(): Locale {
  try {
    const requested = new URLSearchParams(window.location.search).get("lang");
    if (requested === "en" || requested === "ar") {
      localStorage.setItem(STORAGE_KEY, requested);
      return requested;
    }
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "ar") return saved;
  } catch {
    return "en";
  }
  return navigator.language.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function translate(locale: Locale, key: string, vars?: Record<string, string | number>): string {
  const value = lookup(dictionaries[locale].strings, key) ?? lookup(dictionaries.en.strings, key);
  const template = value == null ? key : String(value);
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name) => (vars[name] == null ? "" : String(vars[name])));
}

export function presentError(locale: Locale, error: unknown, fallbackKey: string): string {
  const message = error instanceof Error ? error.message : "";
  const key = KNOWN_ERRORS[message];
  if (key) return translate(locale, key);
  if (message) return message;
  return translate(locale, fallbackKey);
}

function lookup(table: Tree, key: string): string | undefined {
  const value = key.split(".").reduce<string | Tree | undefined>((node, part) => {
    if (!node || typeof node === "string") return undefined;
    return node[part];
  }, table);
  return typeof value === "string" ? value : undefined;
}
