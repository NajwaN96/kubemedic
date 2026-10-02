const STORAGE_KEY = "kubemedic.lang";

const LOCALES = {
  en: {
    dir: "ltr",
    label: "English",
    strings: {
      appName: "KubeMedic",
      skip: "Skip to content",
      nav: {
        overview: "Overview",
        investigations: "Investigations",
        remediations: "Remediations",
        observability: "Observability",
        system: "System Status",
      },
      header: {
        environment: "Environment",
        kubernetes: "Kubernetes",
        menu: "Menu",
        closeMenu: "Close menu",
        collapse: "Collapse sidebar",
        expand: "Expand sidebar",
        language: "Language",
      },
      cluster: { connected: "Connected", disconnected: "Disconnected" },
      pages: {
        overview: "Overview",
        investigations: "Investigations",
        investigation: "Investigation",
        remediations: "Remediations",
        remediation: "Remediation",
        observability: "Observability",
        system: "System Status",
      },
      overview: {
        leadHealthy: "All monitored workloads are currently healthy.",
        leadActive: "{count} active incident needs attention.",
        leadActivePlural: "{count} active incidents need attention.",
        active: "Active Incidents",
        recovering: "Recovering",
        resolved: "Resolved",
        criticalHigh: "Critical / High",
        kubernetes: "Kubernetes",
        remediation: "Remediation",
        ai: "AI",
        serviceHealth: "Service health",
        serviceHint: "Derived from the cluster connection and open investigations. Replica counts are not invented here.",
        activeTitle: "Active incidents",
        recent: "Recent resolved",
        noActive: "No active incidents",
        noActiveBody: "All monitored workloads are currently healthy.",
      },
      health: {
        taskflowApi: "TaskFlow API",
        taskflowFrontend: "TaskFlow Frontend",
        postgresql: "PostgreSQL",
        kubemedic: "KubeMedic",
        watcher: "KubeMedic Watcher",
        prometheus: "Prometheus",
        grafana: "Grafana",
        ai: "AI Integration",
        remediation: "Remediation",
        kubernetes: "Kubernetes",
        healthy: "Healthy",
        unhealthy: "Unhealthy",
        degraded: "Degraded",
        recovering: "Recovering",
        unavailable: "Unavailable",
        disabled: "Disabled",
        enabled: "Enabled",
        connected: "Connected",
        disconnected: "Disconnected",
        notChecked: "Not checked",
        noActive: "No active incidents",
        activeOn: "Active incident on this workload",
        apiOk: "API responded",
        watcherDetail: "Uses the same cluster connection as the API. Watcher internals are not queried separately.",
        labLink: "Local lab link. This page does not probe the service.",
        openGrafana: "Open Grafana",
        openPrometheus: "Open Prometheus",
        metricsTaskflow: "TaskFlow metrics",
        metricsKubemedic: "KubeMedic metrics",
        metricsHint: "Detailed charts stay in Grafana.",
      },
      filters: {
        status: "Status",
        severity: "Severity",
        issue: "Issue Type",
        resource: "Resource",
        search: "Search",
        searchPlaceholder: "ID, resource, or issue",
        all: "All",
        clear: "Clear Filters",
        cleared: "Filters cleared.",
      },
      columns: {
        id: "ID",
        issue: "Issue",
        resource: "Affected Resource",
        severity: "Severity",
        status: "Status",
        detected: "Detected",
        updated: "Updated",
        source: "Analysis Source",
        action: "Action",
        target: "Target",
        approver: "Approver",
        created: "Created",
        verified: "Verified",
      },
      status: {
        open: "Open",
        recovering: "Recovering",
        resolved: "Resolved",
        proposed: "Proposed",
        approved: "Approved",
        executing: "Executing",
        succeeded: "Succeeded",
        failed: "Failed",
        verified: "Verified",
        cancelled: "Cancelled",
      },
      severity: {
        critical: "Critical",
        high: "High",
        medium: "Medium",
        low: "Low",
        informational: "Informational",
      },
      source: {
        rules: "Rule-Based Analysis",
        both: "Rules + AI",
      },
      issues: {
        CrashLoopBackOff: "Container repeatedly crashing",
        ImagePullBackOff: "Unable to pull container image",
        ErrImagePull: "Unable to pull container image",
        OOMKilled: "Container exceeded memory limit",
        FailedScheduling: "Pod could not be scheduled",
        ReadinessProbeFailed: "Application is not ready",
        LivenessProbeFailed: "Liveness check failed",
        DatabaseConnectivity: "Database connection problem",
        CreateContainerConfigError: "Container configuration is invalid",
        CreateContainerError: "Container could not be created",
        FailedMount: "Volume could not be mounted",
        RepeatedRestarts: "Container keeps restarting",
        UnavailableReplicas: "Deployment is short of ready Pods",
      },
      explain: {
        CrashLoopBackOff: "A container starts, exits, and Kubernetes starts it again.",
        ImagePullBackOff: "Kubernetes cannot download the container image, so the Pod cannot start.",
        ErrImagePull: "Kubernetes cannot download the container image, so the Pod cannot start.",
        OOMKilled: "The container used more memory than its limit and was stopped.",
        FailedScheduling: "The scheduler could not place this Pod on a node.",
        ReadinessProbeFailed: "The application is running, but it is not ready to receive traffic.",
        LivenessProbeFailed: "The health check failed, so Kubernetes restarts the container.",
        DatabaseConnectivity: "The application cannot reach its database.",
        CreateContainerConfigError: "Kubernetes could not create the container because configuration is missing or invalid.",
        CreateContainerError: "Kubernetes could not start the container from its specification.",
        FailedMount: "A volume the Pod needs is not available.",
        RepeatedRestarts: "The container keeps restarting without a more specific waiting reason.",
        UnavailableReplicas: "The Deployment has fewer ready Pods than requested.",
      },
      current: {
        open: "Still failing",
        recovering: "Recovering",
        resolved: "Resolved",
      },
      detail: {
        what: "What happened?",
        current: "Current Status",
        cause: "Likely Cause",
        causeNote: "This comes from deterministic rules and Kubernetes evidence.",
        evidence: "Evidence",
        timeline: "Timeline",
        remediation: "Remediation",
        ai: "AI-Assisted Analysis",
        rules: "Rule-Based Analysis",
        resolution: "Resolution",
        technical: "Technical Details",
        showTechnical: "Show technical details",
        reason: "Kubernetes reason",
        detected: "Detected",
        resource: "Affected resource",
        noEvidence: "No structured evidence was stored.",
        noTimeline: "No timeline entries were recorded.",
        noResolution: "This incident is not resolved yet.",
        noProposal: "No remediation proposal. This investigation stays informational.",
        recommended: "Recommended actions",
        occurrences: "Occurrences",
        container: "Container",
        namespace: "Namespace",
        events: "Kubernetes events",
        logs: "Logs",
        previousLogs: "Previous container",
        currentLogs: "Current container",
        noEvents: "No Kubernetes events were attached.",
        noLogs: "No container logs were collected.",
        audit: "Audit and resolution",
        markResolved: "Mark resolved",
        resolveTitle: "Mark this investigation resolved?",
        resolveBody: "This updates the KubeMedic record only. Kubernetes objects are not changed.",
        confirmResolve: "Mark resolved",
        runAi: "Run AI analysis",
        aiOptional: "Optional interpretation of the same evidence. It is not a source of truth and it cannot change Kubernetes.",
        aiDisabled: "AI analysis disabled",
        aiDisabledBody: "KubeMedic continues to investigate incidents using deterministic rules and Kubernetes evidence.",
        aiUnavailable: "No AI analysis available.",
        aiUnavailableBody: "The rule-based investigation remains the operational record.",
        provider: "Provider",
        model: "Model",
        confidence: "Confidence",
        supporting: "Supporting evidence",
        factors: "Contributing factors",
        backInvestigations: "Investigations",
        backOverview: "Overview",
        notFound: "No investigation {id} was found.",
        exactTime: "Exact timestamps",
      },
      remediation: {
        disabled: "Remediation disabled",
        disabledBody: "Human-approved remediation is currently disabled by system configuration.",
        safety: "A proposal is a typed action. KubeMedic does not change the Deployment unless a person confirms it and remediation is enabled.",
        human: "Human Approval Required",
        recommended: "Recommended action",
        why: "Why",
        target: "Target Deployment",
        policy: "Policy validation",
        policyBody: "Allowlist: restart, rollback, or scale. The watcher account stays read-only. Approval is stored only after a person confirms the named action.",
        approval: "Human approval",
        execution: "Execution",
        verification: "Verification",
        before: "Before state",
        after: "After state",
        audit: "Audit Trail",
        none: "No remediation proposals.",
        noneMatch: "No remediation records match these filters.",
        openInvestigation: "Open investigation",
        approve: "Approve",
        cancel: "Cancel",
        cancelProposal: "Cancel proposal",
        cancelTitle: "Cancel this proposal?",
        cancelBody: "The proposal stays in the audit trail and will not be executed.",
        confirmCancel: "Cancel proposal",
        willModify: "This action will modify the Kubernetes Deployment.",
        approvedBy: "Approved by",
        approvalNote: "Approval note",
        nameHint: "Short name. Not a password or token.",
        notApproved: "Not approved yet.",
        notExecuted: "Not executed.",
        notVerified: "Not verified yet.",
        recordedDisabled: "This proposal is recorded. Remediation is disabled, so KubeMedic will not change the Deployment.",
        notFound: "No remediation {id} was found.",
        emptySnapshot: "No audit snapshot yet.",
        images: "Images",
        replicas: "Replicas",
        ready: "Ready",
        updated: "Updated",
        revision: "Revision",
        generation: "Generation",
        observed: "Observed generation",
      },
      actions: {
        rollback_deployment: "Rollback Deployment",
        restart_deployment: "Restart Deployment",
        scale_deployment: "Scale Deployment",
      },
      approveTitle: {
        rollback_deployment: "Approve rollback?",
        restart_deployment: "Approve restart?",
        scale_deployment: "Approve scale?",
      },
      approveButton: {
        rollback_deployment: "Approve rollback",
        restart_deployment: "Approve restart",
        scale_deployment: "Approve scale",
      },
      observability: {
        intro: "Grafana remains the detailed metrics tool. KubeMedic does not rebuild those dashboards.",
        prometheus: "Prometheus status",
        grafana: "Grafana status",
        taskflow: "TaskFlow metrics status",
        kubemedic: "KubeMedic metrics status",
        notProbed: "Not checked from this page. Use the lab port-forward when it is running.",
      },
      system: {
        intro: "Intentionally disabled AI and remediation are safety states, not failures.",
      },
      empty: {
        investigations: "No investigations yet.",
        filters: "No investigations match these filters.",
        ai: "No AI analysis available.",
      },
      loading: {
        page: "Loading…",
        investigations: "Loading investigations…",
      },
      errors: {
        investigations: "Unable to load investigations.",
        investigation: "Unable to load this investigation.",
        remediations: "Unable to load remediations.",
        generic: "Unable to load this page.",
        technical: "Technical detail",
      },
      notice: {
        approved: "Remediation approved.",
        approveFailed: "Failed to approve remediation.",
        cancelled: "Proposal cancelled.",
        cancelFailed: "Failed to cancel the proposal.",
        refreshed: "Investigation refreshed.",
        filters: "Filters cleared.",
        resolved: "Investigation marked resolved.",
        resolveFailed: "Failed to mark the investigation resolved.",
        aiFailed: "AI analysis did not run. The rule-based investigation is unchanged.",
      },
      common: {
        refresh: "Refresh",
        retry: "Retry",
        cancel: "Cancel",
        close: "Close",
        lastUpdated: "Last updated",
        none: "None",
        yes: "Yes",
        no: "No",
      },
    },
    phrases: {},
  },
  ar: {
    dir: "rtl",
    label: "العربية",
    strings: {
      appName: "KubeMedic",
      skip: "تخطي إلى المحتوى",
      nav: {
        overview: "نظرة عامة",
        investigations: "التحقيقات",
        remediations: "المعالجات",
        observability: "المراقبة",
        system: "حالة النظام",
      },
      header: {
        environment: "البيئة",
        kubernetes: "Kubernetes",
        menu: "القائمة",
        closeMenu: "إغلاق القائمة",
        collapse: "طي الشريط الجانبي",
        expand: "توسيع الشريط الجانبي",
        language: "اللغة",
      },
      cluster: { connected: "متصل", disconnected: "غير متصل" },
      pages: {
        overview: "نظرة عامة",
        investigations: "التحقيقات",
        investigation: "التحقيق",
        remediations: "المعالجات",
        remediation: "المعالجة",
        observability: "المراقبة",
        system: "حالة النظام",
      },
      overview: {
        leadHealthy: "جميع الخدمات التي تتم مراقبتها تعمل بشكل سليم حالياً.",
        leadActive: "يوجد حادث نشط واحد يحتاج إلى متابعة.",
        leadActivePlural: "توجد {count} حوادث نشطة تحتاج إلى متابعة.",
        active: "الحوادث النشطة",
        recovering: "قيد التعافي",
        resolved: "تم الحل",
        criticalHigh: "حرج / مرتفع",
        kubernetes: "Kubernetes",
        remediation: "المعالجة",
        ai: "الذكاء الاصطناعي",
        serviceHealth: "صحة الخدمات",
        serviceHint: "مستمدة من اتصال العنقود والحوادث المفتوحة. لا تُخترع أعداد النسخ هنا.",
        activeTitle: "الحوادث النشطة",
        recent: "حوادث تم حلها مؤخراً",
        noActive: "لا توجد حوادث نشطة",
        noActiveBody: "جميع الخدمات التي تتم مراقبتها تعمل بشكل سليم حالياً.",
      },
      health: {
        taskflowApi: "TaskFlow API",
        taskflowFrontend: "TaskFlow Frontend",
        postgresql: "PostgreSQL",
        kubemedic: "KubeMedic",
        watcher: "KubeMedic Watcher",
        prometheus: "Prometheus",
        grafana: "Grafana",
        ai: "تكامل الذكاء الاصطناعي",
        remediation: "المعالجة",
        kubernetes: "Kubernetes",
        healthy: "سليم",
        unhealthy: "غير سليم",
        degraded: "متدهور",
        recovering: "قيد التعافي",
        unavailable: "غير متاح",
        disabled: "معطّل",
        enabled: "مفعّل",
        connected: "متصل",
        disconnected: "غير متصل",
        notChecked: "لم يُفحص",
        noActive: "لا توجد حوادث نشطة",
        activeOn: "يوجد حادث نشط على هذا العبء",
        apiOk: "استجاب الـ API",
        watcherDetail: "يستخدم اتصال العنقود نفسه الذي يستخدمه الـ API. لا تُستعلم تفاصيل المراقب بشكل منفصل.",
        labLink: "رابط المختبر المحلي. هذه الصفحة لا تفحص الخدمة.",
        openGrafana: "فتح Grafana",
        openPrometheus: "فتح Prometheus",
        metricsTaskflow: "مقاييس TaskFlow",
        metricsKubemedic: "مقاييس KubeMedic",
        metricsHint: "الرسوم التفصيلية تبقى في Grafana.",
      },
      filters: {
        status: "الحالة",
        severity: "درجة الخطورة",
        issue: "نوع المشكلة",
        resource: "المورد",
        search: "بحث",
        searchPlaceholder: "المعرّف أو المورد أو نوع المشكلة",
        all: "الكل",
        clear: "مسح عوامل التصفية",
        cleared: "تم مسح عوامل التصفية.",
      },
      columns: {
        id: "المعرّف",
        issue: "المشكلة",
        resource: "المورد المتأثر",
        severity: "درجة الخطورة",
        status: "الحالة",
        detected: "وقت الرصد",
        updated: "آخر تحديث",
        source: "مصدر التحليل",
        action: "الإجراء",
        target: "الهدف",
        approver: "المعتمِد",
        created: "تاريخ الإنشاء",
        verified: "تم التحقق",
      },
      status: {
        open: "مفتوح",
        recovering: "قيد التعافي",
        resolved: "تم الحل",
        proposed: "مقترح",
        approved: "تمت الموافقة",
        executing: "قيد التنفيذ",
        succeeded: "نجح التنفيذ",
        failed: "فشل",
        verified: "تم التحقق",
        cancelled: "ملغى",
      },
      severity: {
        critical: "حرج",
        high: "مرتفع",
        medium: "متوسط",
        low: "منخفض",
        informational: "معلوماتي",
      },
      source: {
        rules: "التحليل القائم على القواعد",
        both: "قواعد + ذكاء اصطناعي",
      },
      issues: {
        CrashLoopBackOff: "الحاوية تتوقف بشكل متكرر",
        ImagePullBackOff: "تعذر تحميل صورة الحاوية",
        ErrImagePull: "تعذر تحميل صورة الحاوية",
        OOMKilled: "تجاوزت الحاوية حد الذاكرة",
        FailedScheduling: "تعذر جدولة الـ Pod",
        ReadinessProbeFailed: "التطبيق غير جاهز لاستقبال الطلبات",
        LivenessProbeFailed: "فشل فحص الحياة",
        DatabaseConnectivity: "مشكلة في الاتصال بقاعدة البيانات",
        CreateContainerConfigError: "إعداد الحاوية غير صالح",
        CreateContainerError: "تعذر إنشاء الحاوية",
        FailedMount: "تعذر تركيب وحدة التخزين",
        RepeatedRestarts: "الحاوية تُعاد تشغيلها باستمرار",
        UnavailableReplicas: "الـ Deployment أقل من عدد الـ Pods الجاهزة",
      },
      explain: {
        CrashLoopBackOff: "تبدأ الحاوية ثم تتوقف، ويعيد Kubernetes تشغيلها.",
        ImagePullBackOff: "يتعذر على Kubernetes تنزيل صورة الحاوية، لذلك لا يبدأ الـ Pod.",
        ErrImagePull: "يتعذر على Kubernetes تنزيل صورة الحاوية، لذلك لا يبدأ الـ Pod.",
        OOMKilled: "استخدمت الحاوية ذاكرة أكثر من حدها فأُوقفت.",
        FailedScheduling: "تعذر على المجدول وضع هذا الـ Pod على عقدة.",
        ReadinessProbeFailed: "التطبيق يعمل، لكنه غير جاهز لاستقبال الطلبات.",
        LivenessProbeFailed: "فشل فحص الصحة، لذلك يعيد Kubernetes تشغيل الحاوية.",
        DatabaseConnectivity: "لا يستطيع التطبيق الوصول إلى قاعدة البيانات.",
        CreateContainerConfigError: "تعذر إنشاء الحاوية لأن الإعداد ناقص أو غير صالح.",
        CreateContainerError: "تعذر بدء الحاوية من مواصفاتها.",
        FailedMount: "وحدة التخزين التي يحتاجها الـ Pod غير متاحة.",
        RepeatedRestarts: "تُعاد تشغيل الحاوية باستمرار دون سبب انتظار أوضح.",
        UnavailableReplicas: "عدد الـ Pods الجاهزة في الـ Deployment أقل من المطلوب.",
      },
      current: {
        open: "لا يزال العطل قائماً",
        recovering: "قيد التعافي",
        resolved: "تم الحل",
      },
      detail: {
        what: "ماذا حدث؟",
        current: "الحالة الحالية",
        cause: "السبب المحتمل",
        causeNote: "هذا ناتج عن القواعد الحتمية وأدلة Kubernetes.",
        evidence: "الأدلة",
        timeline: "التسلسل الزمني",
        remediation: "المعالجة",
        ai: "تحليل مساعد بالذكاء الاصطناعي",
        rules: "التحليل القائم على القواعد",
        resolution: "الحل",
        technical: "التفاصيل التقنية",
        showTechnical: "عرض التفاصيل التقنية",
        reason: "سبب Kubernetes",
        detected: "وقت الرصد",
        resource: "المورد المتأثر",
        noEvidence: "لم تُحفظ أدلة منظمة.",
        noTimeline: "لا توجد أحداث في التسلسل الزمني.",
        noResolution: "لم يُحل هذا الحادث بعد.",
        noProposal: "لا يوجد مقترح معالجة. يبقى هذا التحقيق معلوماتياً.",
        recommended: "الإجراءات المقترحة",
        occurrences: "مرات التكرار",
        container: "الحاوية",
        namespace: "النطاق",
        events: "أحداث Kubernetes",
        logs: "السجلات",
        previousLogs: "الحاوية السابقة",
        currentLogs: "الحاوية الحالية",
        noEvents: "لم تُرفق أحداث Kubernetes.",
        noLogs: "لم تُجمع سجلات الحاوية.",
        audit: "سجل العمليات والحل",
        markResolved: "تعليم كمحلول",
        resolveTitle: "تعليم هذا التحقيق كمحلول؟",
        resolveBody: "يحدّث هذا سجل KubeMedic فقط. لا تتغير كائنات Kubernetes.",
        confirmResolve: "تعليم كمحلول",
        runAi: "تشغيل التحليل بالذكاء الاصطناعي",
        aiOptional: "تفسير إضافي للأدلة نفسها. ليس مصدراً قاطعاً ولا يستطيع تغيير Kubernetes.",
        aiDisabled: "تحليل الذكاء الاصطناعي غير مفعّل",
        aiDisabledBody: "يستمر KubeMedic في تحليل الحوادث باستخدام القواعد والأدلة القادمة من Kubernetes.",
        aiUnavailable: "لا يتوفر تحليل بالذكاء الاصطناعي.",
        aiUnavailableBody: "يبقى التحقيق القائم على القواعد هو السجل التشغيلي.",
        provider: "المزوّد",
        model: "النموذج",
        confidence: "درجة الثقة",
        supporting: "أدلة داعمة",
        factors: "عوامل مساهمة",
        backInvestigations: "التحقيقات",
        backOverview: "نظرة عامة",
        notFound: "لم يُعثر على التحقيق {id}.",
        exactTime: "الطوابع الزمنية الدقيقة",
      },
      remediation: {
        disabled: "المعالجة معطلة حالياً",
        disabledBody: "ميزة المعالجة التي تتطلب موافقة بشرية معطلة من إعدادات النظام.",
        safety: "المقترح إجراء محدد النوع. لا يغيّر KubeMedic الـ Deployment إلا إذا أكّد شخص ذلك وكانت المعالجة مفعّلة.",
        human: "يتطلب موافقة بشرية",
        recommended: "الإجراء المقترح",
        why: "السبب",
        target: "الـ Deployment المستهدف",
        policy: "التحقق من السياسة",
        policyBody: "القائمة المسموحة: إعادة التشغيل، أو الرجوع إلى إصدار سابق، أو تغيير عدد النسخ. حساب المراقب يبقى للقراءة فقط. تُحفظ الموافقة فقط بعد أن يؤكّد شخص الإجراء المحدد.",
        approval: "الموافقة البشرية",
        execution: "التنفيذ",
        verification: "التحقق",
        before: "الحالة قبل التنفيذ",
        after: "الحالة بعد التنفيذ",
        audit: "سجل العمليات",
        none: "لا توجد مقترحات معالجة.",
        noneMatch: "لا توجد سجلات معالجة مطابقة لعوامل التصفية.",
        openInvestigation: "فتح التحقيق",
        approve: "موافقة",
        cancel: "إلغاء",
        cancelProposal: "إلغاء المقترح",
        cancelTitle: "إلغاء هذا المقترح؟",
        cancelBody: "يبقى المقترح في سجل العمليات ولن يُنفَّذ.",
        confirmCancel: "إلغاء المقترح",
        willModify: "سيؤدي هذا الإجراء إلى تعديل الـ Deployment في Kubernetes.",
        approvedBy: "اعتمد بواسطة",
        approvalNote: "ملاحظة الموافقة",
        nameHint: "اسم قصير. ليس كلمة مرور أو رمزاً.",
        notApproved: "لم تُمنح الموافقة بعد.",
        notExecuted: "لم يُنفَّذ.",
        notVerified: "لم يُتحقق بعد.",
        recordedDisabled: "هذا المقترح مسجّل. المعالجة معطلة، لذلك لن يغيّر KubeMedic الـ Deployment.",
        notFound: "لم يُعثر على المعالجة {id}.",
        emptySnapshot: "لا توجد لقطة تدقيق بعد.",
        images: "الصور",
        replicas: "النسخ",
        ready: "الجاهزة",
        updated: "المحدَّثة",
        revision: "المراجعة",
        generation: "الجيل",
        observed: "الجيل المرصود",
      },
      actions: {
        rollback_deployment: "الرجوع إلى إصدار سابق للـ Deployment",
        restart_deployment: "إعادة تشغيل الـ Deployment",
        scale_deployment: "تغيير عدد نسخ الـ Deployment",
      },
      approveTitle: {
        rollback_deployment: "الموافقة على الرجوع إلى إصدار سابق؟",
        restart_deployment: "الموافقة على إعادة التشغيل؟",
        scale_deployment: "الموافقة على تغيير عدد النسخ؟",
      },
      approveButton: {
        rollback_deployment: "الموافقة على الرجوع",
        restart_deployment: "الموافقة على إعادة التشغيل",
        scale_deployment: "الموافقة على تغيير العدد",
      },
      observability: {
        intro: "تبقى Grafana أداة المقاييس التفصيلية. لا يعيد KubeMedic بناء تلك اللوحات.",
        prometheus: "حالة Prometheus",
        grafana: "حالة Grafana",
        taskflow: "حالة مقاييس TaskFlow",
        kubemedic: "حالة مقاييس KubeMedic",
        notProbed: "لم تُفحص من هذه الصفحة. استخدم تحويل المنفذ المحلي عندما يكون المختبر شغّالاً.",
      },
      system: {
        intro: "تعطيل الذكاء الاصطناعي والمعالجة عن قصد حالة سلامة، وليس عطلاً.",
      },
      empty: {
        investigations: "لا توجد تحقيقات بعد.",
        filters: "لا توجد تحقيقات مطابقة لعوامل التصفية.",
        ai: "لا يتوفر تحليل بالذكاء الاصطناعي.",
      },
      loading: {
        page: "جارٍ التحميل…",
        investigations: "جارٍ تحميل التحقيقات…",
      },
      errors: {
        investigations: "تعذر تحميل التحقيقات.",
        investigation: "تعذر تحميل هذا التحقيق.",
        remediations: "تعذر تحميل المعالجات.",
        generic: "تعذر تحميل هذه الصفحة.",
        technical: "تفصيل تقني",
      },
      notice: {
        approved: "تمت الموافقة على المعالجة.",
        approveFailed: "تعذرت الموافقة على المعالجة.",
        cancelled: "أُلغي المقترح.",
        cancelFailed: "تعذر إلغاء المقترح.",
        refreshed: "تم تحديث التحقيق.",
        filters: "تم مسح عوامل التصفية.",
        resolved: "تم تعليم التحقيق كمحلول.",
        resolveFailed: "تعذر تعليم التحقيق كمحلول.",
        aiFailed: "لم يعمل تحليل الذكاء الاصطناعي. التحقيق القائم على القواعد لم يتغير.",
      },
      common: {
        refresh: "تحديث",
        retry: "إعادة المحاولة",
        cancel: "إلغاء",
        close: "إغلاق",
        lastUpdated: "آخر تحديث",
        none: "لا شيء",
        yes: "نعم",
        no: "لا",
      },
    },
    phrases: {},
  },
};

const PHRASES = {
  en: {
    "Failure detected": "Failure detected",
    "Previous logs collected": "Previous logs collected",
    "Current logs collected": "Current logs collected",
    "Container restarted during recovery": "Container restarted during recovery",
    "Affected Pod no longer exists": "Affected Pod no longer exists",
    "Owning workload is healthy": "Owning workload is healthy",
    "Owning workload is still degraded": "Owning workload is still degraded",
    "Affected resource no longer exists": "Affected resource no longer exists",
    "Investigation resolved": "Incident resolved",
    "Current resource is healthy": "Current resource is healthy",
    "Cancelled before execution": "Cancelled before execution",
    "Approved action started": "Approved action started",
    "resolved by operator": "Resolved by an operator",
    "resource remained healthy through the stabilization window": "The resource stayed healthy through the stabilization window",
    "affected Pod was replaced and owning workload is healthy": "The affected Pod was replaced and the owning workload is healthy",
    "affected resource no longer exists": "The affected resource no longer exists",
    "The API container repeatedly exits during startup.": "The API container repeatedly exits during startup.",
    "The container repeatedly starts and exits.": "The container repeatedly starts and exits.",
    "The kubelet could not authenticate to the image registry.": "The kubelet could not authenticate to the image registry.",
    "The image name or tag does not exist in the registry.": "The image name or tag does not exist in the registry.",
    "The kubelet could not reach the image registry.": "The kubelet could not reach the image registry.",
    "The kubelet could not pull the container image.": "The kubelet could not pull the container image.",
    "The container exceeded its allowed memory and the kernel killed it.": "The container exceeded its allowed memory and the kernel killed it.",
    "The Pod references a Secret that is missing or not visible in the namespace.": "The Pod references a Secret that is missing or not visible in the namespace.",
    "The Pod references a ConfigMap that is missing.": "The Pod references a ConfigMap that is missing.",
    "Kubernetes could not build the container configuration from the Pod spec.": "Kubernetes could not build the container configuration from the Pod spec.",
    "A volume mount is waiting on a PersistentVolumeClaim.": "A volume mount is waiting on a PersistentVolumeClaim.",
    "A volume mount references a Secret that is missing or unreadable.": "A volume mount references a Secret that is missing or unreadable.",
    "A volume mount references a ConfigMap that is missing.": "A volume mount references a ConfigMap that is missing.",
    "Kubernetes could not mount a volume required by the Pod.": "Kubernetes could not mount a volume required by the Pod.",
    "The scheduler did not place the Pod because CPU requests do not fit the nodes.": "The scheduler did not place the Pod because CPU requests do not fit the nodes.",
    "The scheduler did not place the Pod because memory requests do not fit the nodes.": "The scheduler did not place the Pod because memory requests do not fit the nodes.",
    "The scheduler rejected the nodes because of taints the Pod does not tolerate.": "The scheduler rejected the nodes because of taints the Pod does not tolerate.",
    "The Pod node selector or affinity did not match any node.": "The Pod node selector or affinity did not match any node.",
    "The scheduler is waiting on a PersistentVolumeClaim constraint.": "The scheduler is waiting on a PersistentVolumeClaim constraint.",
    "The scheduler could not bind the Pod to a node.": "The scheduler could not bind the Pod to a node.",
    "The readiness probe failed, so the Pod is not receiving Service traffic.": "The readiness probe failed, so the Pod is not receiving Service traffic.",
    "The readiness probe failed. Logs show the process cannot reach PostgreSQL.": "The readiness probe failed. Logs show the process cannot reach PostgreSQL.",
    "The liveness probe did not succeed, so the kubelet restarts the container.": "The liveness probe did not succeed, so the kubelet restarts the container.",
    "Application logs show a database connection failure. Credentials were not collected.": "Application logs show a database connection failure. Credentials were not collected.",
    "The container is restarting repeatedly without a more specific waiting reason.": "The container is restarting repeatedly without a more specific waiting reason.",
    "The collected Pod status and events match this condition.": "The collected Pod status and events match this condition.",
    "The container is in CrashLoopBackOff and exits during startup.": "The container is in CrashLoopBackOff and exits during startup.",
    "The container was OOMKilled.": "The container was OOMKilled.",
    "Kubernetes could not create the container because its configuration is invalid.": "Kubernetes could not create the container because its configuration is invalid.",
    "A volume required by the Pod is not mounting.": "A volume required by the Pod is not mounting.",
    "The Pod is Pending because it cannot be scheduled.": "The Pod is Pending because it cannot be scheduled.",
    "The readiness probe is failing.": "The readiness probe is failing.",
    "The liveness probe is failing and Kubernetes is restarting the container.": "The liveness probe is failing and Kubernetes is restarting the container.",
    "Dependency failure: the application cannot reach PostgreSQL.": "Dependency failure: the application cannot reach PostgreSQL.",
    "The Deployment has fewer ready replicas than desired.": "The Deployment has fewer ready replicas than desired.",
    "Deployment wants zero replicas. The bounded safe count for this lab is 1.": "The Deployment wants zero replicas. The bounded safe count for this lab is 1.",
    "CrashLoopBackOff started on a newer Deployment revision.": "CrashLoopBackOff started on a newer Deployment revision.",
    "The Deployment is unhealthy and a rollout restart is the allowlisted action.": "The Deployment is unhealthy and a rollout restart is the allowlisted action.",
    "Inspect previous container logs.": "Inspect previous container logs.",
    "Verify environment configuration.": "Verify environment configuration.",
    "Verify application startup dependencies.": "Verify application startup dependencies.",
    "Verify PostgreSQL availability.": "Verify PostgreSQL availability.",
    "Verify the database hostname.": "Verify the database hostname.",
    "Pod phase": "Pod phase",
    "Waiting reason": "Waiting reason",
    "Termination reason": "Termination reason",
    "Exit code": "Exit code",
    "Restart count": "Restart count",
    Image: "Image",
    "Image ID": "Image ID",
    "Memory limit": "Memory limit",
    Node: "Node",
    Deployment: "Deployment",
    Owner: "Owner",
    "registry authentication": "registry authentication",
    "invalid image or tag": "invalid image or tag",
    "registry unavailable": "registry unavailable",
    "image pull failed": "image pull failed",
  },
  ar: {
    "Failure detected": "تم رصد العطل",
    "Previous logs collected": "جُمعت سجلات الحاوية السابقة",
    "Current logs collected": "جُمعت السجلات الحالية",
    "Container restarted during recovery": "أُعيد تشغيل الحاوية أثناء التعافي",
    "Affected Pod no longer exists": "الـ Pod المتأثر لم يعد موجوداً",
    "Owning workload is healthy": "العبء المالِك سليم",
    "Owning workload is still degraded": "العبء المالِك ما زال متدهوراً",
    "Affected resource no longer exists": "المورد المتأثر لم يعد موجوداً",
    "Investigation resolved": "تم حل الحادث",
    "Current resource is healthy": "المورد الحالي سليم",
    "Cancelled before execution": "أُلغي قبل التنفيذ",
    "Approved action started": "بدأ تنفيذ الإجراء المعتمد",
    "resolved by operator": "تم الحل بواسطة المشغّل",
    "resource remained healthy through the stabilization window": "بقي المورد سليماً طوال نافذة الاستقرار",
    "affected Pod was replaced and owning workload is healthy": "استُبدل الـ Pod المتأثر والعبء المالِك سليم",
    "affected resource no longer exists": "المورد المتأثر لم يعد موجوداً",
    "The API container repeatedly exits during startup.": "حاوية الـ API تتوقف بشكل متكرر أثناء الإقلاع.",
    "The container repeatedly starts and exits.": "الحاوية تبدأ ثم تتوقف بشكل متكرر.",
    "The kubelet could not authenticate to the image registry.": "تعذر على kubelet المصادقة لدى سجل الصور.",
    "The image name or tag does not exist in the registry.": "اسم الصورة أو الوسم غير موجود في السجل.",
    "The kubelet could not reach the image registry.": "تعذر على kubelet الوصول إلى سجل الصور.",
    "The kubelet could not pull the container image.": "تعذر على kubelet سحب صورة الحاوية.",
    "The container exceeded its allowed memory and the kernel killed it.": "تجاوزت الحاوية الذاكرة المسموحة وأنهى النظام العملية.",
    "The Pod references a Secret that is missing or not visible in the namespace.": "يشير الـ Pod إلى Secret غير موجود أو غير ظاهر في النطاق.",
    "The Pod references a ConfigMap that is missing.": "يشير الـ Pod إلى ConfigMap غير موجود.",
    "Kubernetes could not build the container configuration from the Pod spec.": "تعذر على Kubernetes بناء إعداد الحاوية من مواصفات الـ Pod.",
    "A volume mount is waiting on a PersistentVolumeClaim.": "تركيب وحدة التخزين ينتظر PersistentVolumeClaim.",
    "A volume mount references a Secret that is missing or unreadable.": "يشير تركيب وحدة التخزين إلى Secret مفقود أو غير قابل للقراءة.",
    "A volume mount references a ConfigMap that is missing.": "يشير تركيب وحدة التخزين إلى ConfigMap مفقود.",
    "Kubernetes could not mount a volume required by the Pod.": "تعذر على Kubernetes تركيب وحدة تخزين يحتاجها الـ Pod.",
    "The scheduler did not place the Pod because CPU requests do not fit the nodes.": "لم يضع المجدول الـ Pod لأن طلبات المعالج لا تتسع في العقد.",
    "The scheduler did not place the Pod because memory requests do not fit the nodes.": "لم يضع المجدول الـ Pod لأن طلبات الذاكرة لا تتسع في العقد.",
    "The scheduler rejected the nodes because of taints the Pod does not tolerate.": "رفض المجدول العقد بسبب taints لا يتحملها الـ Pod.",
    "The Pod node selector or affinity did not match any node.": "محدد العقدة أو التقارب لم يطابق أي عقدة.",
    "The scheduler is waiting on a PersistentVolumeClaim constraint.": "المجدول ينتظر قيداً متعلقاً بـ PersistentVolumeClaim.",
    "The scheduler could not bind the Pod to a node.": "تعذر على المجدول ربط الـ Pod بعقدة.",
    "The readiness probe failed, so the Pod is not receiving Service traffic.": "فشل فحص الجاهزية، لذلك لا يستقبل الـ Pod حركة الخدمة.",
    "The readiness probe failed. Logs show the process cannot reach PostgreSQL.": "فشل فحص الجاهزية. تُظهر السجلات أن العملية لا تصل إلى PostgreSQL.",
    "The liveness probe did not succeed, so the kubelet restarts the container.": "لم ينجح فحص الحياة، لذلك يعيد kubelet تشغيل الحاوية.",
    "Application logs show a database connection failure. Credentials were not collected.": "تُظهر سجلات التطبيق فشلاً في الاتصال بقاعدة البيانات. لم تُجمع بيانات الاعتماد.",
    "The container is restarting repeatedly without a more specific waiting reason.": "تُعاد تشغيل الحاوية باستمرار دون سبب انتظار أوضح.",
    "The collected Pod status and events match this condition.": "حالة الـ Pod والأحداث المجموعة تطابق هذا الوضع.",
    "The container is in CrashLoopBackOff and exits during startup.": "الحاوية في CrashLoopBackOff وتتوقف أثناء الإقلاع.",
    "The container was OOMKilled.": "أُوقفت الحاوية بسبب نفاد الذاكرة.",
    "Kubernetes could not create the container because its configuration is invalid.": "تعذر إنشاء الحاوية لأن إعدادها غير صالح.",
    "A volume required by the Pod is not mounting.": "وحدة التخزين التي يحتاجها الـ Pod لا تُركَّب.",
    "The Pod is Pending because it cannot be scheduled.": "الـ Pod في حالة Pending لأنه لا يُجدول.",
    "The readiness probe is failing.": "فحص الجاهزية يفشل.",
    "The liveness probe is failing and Kubernetes is restarting the container.": "فحص الحياة يفشل وKubernetes يعيد تشغيل الحاوية.",
    "Dependency failure: the application cannot reach PostgreSQL.": "فشل تبعية: التطبيق لا يصل إلى PostgreSQL.",
    "The Deployment has fewer ready replicas than desired.": "عدد النسخ الجاهزة في الـ Deployment أقل من المطلوب.",
    "Deployment wants zero replicas. The bounded safe count for this lab is 1.": "الـ Deployment يطلب صفر نسخ. العدد الآمن المحدود في هذا المختبر هو 1.",
    "CrashLoopBackOff started on a newer Deployment revision.": "بدأ CrashLoopBackOff على مراجعة أحدث للـ Deployment.",
    "The Deployment is unhealthy and a rollout restart is the allowlisted action.": "الـ Deployment غير سليم، وإعادة تشغيل الطرح هي الإجراء المسموح.",
    "Inspect previous container logs.": "افحص سجلات الحاوية السابقة.",
    "Verify environment configuration.": "تحقق من إعداد البيئة.",
    "Verify application startup dependencies.": "تحقق من اعتماديات إقلاع التطبيق.",
    "Verify PostgreSQL availability.": "تحقق من توفر PostgreSQL.",
    "Verify the database hostname.": "تحقق من اسم مضيف قاعدة البيانات.",
    "Pod phase": "مرحلة الـ Pod",
    "Waiting reason": "سبب الانتظار",
    "Termination reason": "سبب الإيقاف",
    "Exit code": "رمز الخروج",
    "Restart count": "عدد إعادات التشغيل",
    Image: "الصورة",
    "Image ID": "معرّف الصورة",
    "Memory limit": "حد الذاكرة",
    Node: "العقدة",
    Deployment: "Deployment",
    Owner: "المالك",
    "registry authentication": "مصادقة السجل",
    "invalid image or tag": "صورة أو وسم غير صالح",
    "registry unavailable": "السجل غير متاح",
    "image pull failed": "فشل سحب الصورة",
  },
};

let locale = initialLocale();
const listeners = new Set();

function initialLocale() {
  try {
    const requested = new URLSearchParams(window.location.search).get("lang");
    if (requested === "en" || requested === "ar") {
      localStorage.setItem(STORAGE_KEY, requested);
      return requested;
    }
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "ar") return saved;
  } catch (error) {
    return "en";
  }
  const language = (navigator.language || "en").toLowerCase();
  return language.startsWith("ar") ? "ar" : "en";
}

function lookup(table, key) {
  return key.split(".").reduce((node, part) => {
    if (node && Object.prototype.hasOwnProperty.call(node, part)) return node[part];
    return undefined;
  }, table);
}

export function getLocale() {
  return locale;
}

export function localeChoices() {
  return [
    { code: "ar", label: LOCALES.ar.label },
    { code: "en", label: LOCALES.en.label },
  ];
}

export function getDir() {
  return LOCALES[locale].dir;
}

export function localeMeta() {
  return { code: locale, dir: LOCALES[locale].dir, label: LOCALES[locale].label };
}

export function t(key, vars) {
  const value = lookup(LOCALES[locale].strings, key) ?? lookup(LOCALES.en.strings, key);
  const template = value == null ? key : String(value);
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name) => (vars[name] == null ? "" : String(vars[name])));
}

export function phrase(text) {
  if (text == null || text === "") return "";
  const raw = String(text);
  const table = PHRASES[locale] || PHRASES.en;
  if (table[raw]) return table[raw];
  const observed = raw.match(/^(.+) observed$/);
  if (observed) {
    return locale === "ar" ? `تم تأكيد ${observed[1]}` : `${observed[1]} confirmed`;
  }
  const approved = raw.match(/^Approved by (.+)$/);
  if (approved) {
    return locale === "ar" ? `تمت الموافقة بواسطة ${approved[1]}` : `Approved by ${approved[1]}`;
  }
  const ready = raw.match(/^Ready replicas are (.+) of (.+)\.$/);
  if (ready) {
    return locale === "ar"
      ? `النسخ الجاهزة ${ready[1]} من ${ready[2]}.`
      : `Ready replicas are ${ready[1]} of ${ready[2]}.`;
  }
  const restarts = raw.match(/^The container has restarted (.+) times\.$/);
  if (restarts) {
    return locale === "ar"
      ? `أُعيد تشغيل الحاوية ${restarts[1]} مرة.`
      : `The container has restarted ${restarts[1]} times.`;
  }
  const detected = raw.match(/^KubeMedic detected (.+)\.$/);
  if (detected) {
    return locale === "ar" ? `رصد KubeMedic الحالة ${detected[1]}.` : raw;
  }
  const pulling = raw.match(/^The container cannot start because pulling (.+) failed \((.+)\)\.$/);
  if (pulling) {
    const category = phrase(pulling[2]);
    return locale === "ar"
      ? `لا تبدأ الحاوية لأن سحب ${pulling[1]} فشل (${category}).`
      : `The container cannot start because pulling ${pulling[1]} failed (${category}).`;
  }
  const memory = raw.match(/^The container exceeded its allowed memory and the kernel killed it\. The container memory limit is (.+)\.$/);
  if (memory) {
    return locale === "ar"
      ? `تجاوزت الحاوية الذاكرة المسموحة وأنهى النظام العملية. حد الذاكرة هو ${memory[1]}.`
      : raw;
  }
  return raw;
}

export function setLocale(next) {
  if (!LOCALES[next] || next === locale) return;
  locale = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch (error) {
    /* ignore private mode */
  }
  applyDocument();
  listeners.forEach((listener) => listener(locale));
}

export function onLocale(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function applyDocument() {
  const meta = LOCALES[locale];
  document.documentElement.lang = locale;
  document.documentElement.dir = meta.dir;
}

export function formatWhen(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value ? String(value) : "—";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function formatClock(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value ? String(value) : "—";
  return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(date);
}

export function formatExact(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value ? String(value) : "—";
  return date.toISOString();
}

applyDocument();
