package com.example.tasktracker.service;

import com.example.tasktracker.model.Task;
import com.example.tasktracker.model.TaskNotFoundException;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * In-memory хранилище задач. Данные не переживают перезапуск приложения,
 * для учебного проекта этого достаточно и это упрощает запуск контейнера.
 */
@Service
public class TaskService {

    private final Map<Long, Task> tasks = new ConcurrentHashMap<>();
    private final AtomicLong sequence = new AtomicLong();

    public List<Task> findAll() {
        return tasks.values().stream()
                .sorted(Comparator.comparingLong(Task::id))
                .toList();
    }

    public Task findById(long id) {
        Task task = tasks.get(id);
        if (task == null) {
            throw new TaskNotFoundException(id);
        }
        return task;
    }

    public Task create(String title) {
        String normalized = title == null ? "" : title.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("Task title must not be blank");
        }
        long id = sequence.incrementAndGet();
        Task task = new Task(id, normalized, false, Instant.now());
        tasks.put(id, task);
        return task;
    }

    public Task changeStatus(long id, boolean done) {
        findById(id);
        return tasks.computeIfPresent(id, (key, task) -> task.withDone(done));
    }

    public void delete(long id) {
        if (tasks.remove(id) == null) {
            throw new TaskNotFoundException(id);
        }
    }

    public long count() {
        return tasks.size();
    }

    /** Используется в тестах, чтобы каждый тест начинал с пустого хранилища. */
    public void deleteAll() {
        tasks.clear();
    }
}
