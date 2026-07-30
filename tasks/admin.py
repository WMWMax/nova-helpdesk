from django.contrib import admin
from .models import Task, TaskComment, TaskFiles, Solution

# Register your models here.
class TaskCommentInLine(admin.StackedInline):
    model = TaskComment
    extra = 0


class TaskFilesInLine(admin.StackedInline):
    model = TaskFiles
    extra = 0


class TaskAdmin(admin.ModelAdmin):
    inlines = [TaskFilesInLine, TaskCommentInLine]

admin.site.register(Task, TaskAdmin)
admin.site.register(Solution)
