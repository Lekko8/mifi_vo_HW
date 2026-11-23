package com.example.tasktracker.model;

import java.time.Instant;

/**
 * Задача трекера. Иммутабельная запись: изменение статуса создаёт новый экземпляр.
 */
public record Task(long id, String title, boolean done, Instant createdAt) {

    public Task withDone(boolean newDone) {
        return new Task(id, title, newDone, createdAt);
    }
}
