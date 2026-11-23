package com.example.tasktracker.model;

/** Тело запроса на создание или изменение задачи. */
public record TaskRequest(String title, Boolean done) {
}
