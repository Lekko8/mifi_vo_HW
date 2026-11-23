package com.example.tasktracker.service;

import com.example.tasktracker.model.Task;
import com.example.tasktracker.model.TaskNotFoundException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TaskServiceTest {

    private TaskService service;

    @BeforeEach
    void setUp() {
        service = new TaskService();
    }

    @Test
    @DisplayName("create() trims title and returns task with generated id")
    void createStoresTask() {
        Task task = service.create("  write report  ");

        assertEquals(1L, task.id());
        assertEquals("write report", task.title());
        assertFalse(task.done());
        assertEquals(1, service.findAll().size());
    }

    @Test
    @DisplayName("create() rejects blank title")
    void createRejectsBlankTitle() {
        IllegalArgumentException error =
                assertThrows(IllegalArgumentException.class, () -> service.create("   "));

        assertTrue(error.getMessage().contains("blank"));
    }

    @Test
    @DisplayName("findAll() returns tasks ordered by id")
    void findAllReturnsOrderedTasks() {
        service.create("first");
        service.create("second");
        service.create("third");

        List<Task> tasks = service.findAll();

        assertEquals(List.of(1L, 2L, 3L), tasks.stream().map(Task::id).toList());
        assertEquals("second", tasks.get(1).title());
    }

    @Test
    @DisplayName("changeStatus() toggles the done flag")
    void changeStatusUpdatesTask() {
        Task created = service.create("push image");

        Task updated = service.changeStatus(created.id(), true);

        assertTrue(updated.done());
        assertTrue(service.findById(created.id()).done());
        assertEquals("push image", updated.title());
    }

    @Test
    @DisplayName("delete() removes task and fails on unknown id")
    void deleteRemovesTask() {
        Task created = service.create("temporary");

        service.delete(created.id());

        assertEquals(0, service.findAll().size());
        assertThrows(TaskNotFoundException.class, () -> service.findById(created.id()));
    }

    @Test
    @DisplayName("findById() fails for unknown id")
    void findByIdFailsForUnknownId() {
        assertThrows(TaskNotFoundException.class, () -> service.findById(42L));
    }
}
