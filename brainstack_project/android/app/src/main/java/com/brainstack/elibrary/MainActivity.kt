package com.brainstack.elibrary

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Query
import com.google.gson.annotations.SerializedName

private val Maroon = Color(0xFF7A0019)
private val Cream = Color(0xFFF8F4F3)
data class Book(val id:Int,val title:String,val author:String,val category:String,val description:String="")
data class BookResponse(val items:List<Book>,val total:Int,val categories:List<String>)
interface BrainApi { @GET("api/books") suspend fun books(@Query("q") q:String="",@Query("limit") limit:Int=100):BookResponse }
object Api { val service:BrainApi by lazy { Retrofit.Builder().baseUrl(BuildConfig.API_BASE_URL).addConverterFactory(GsonConverterFactory.create()).build().create(BrainApi::class.java) } }

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState:Bundle?) { super.onCreate(savedInstanceState); setContent { BrainStackApp() } }
}

@Composable fun BrainStackApp() {
 var page by remember { mutableStateOf("Home") }; var query by remember { mutableStateOf("") }; var books by remember { mutableStateOf(emptyList<Book>()) }; var status by remember { mutableStateOf("Welcome to BrainStack E-Library") }
 LaunchedEffect(page,query) { if(page=="Explore Books") { try { books=withContext(Dispatchers.IO){Api.service.books(query).items}; status="${books.size} books loaded" } catch(e:Exception){status="Connect the FastAPI backend to load books."} } }
 MaterialTheme(colorScheme=lightColorScheme(primary=Maroon,background=Cream)) {
  Scaffold(containerColor=Cream, topBar={ Column(Modifier.fillMaxWidth().background(Color.White).padding(16.dp)){ Text("BRAIN STACK",fontSize=22.sp,fontWeight=FontWeight.ExtraBold,color=Maroon); Text("E-LIBRARY",fontSize=11.sp,color=Color.Gray) } }, bottomBar={ NavigationBar(containerColor=Color.White){ listOf("Home","Explore Books","AI Assistant","My Library").forEach { item -> NavigationBarItem(selected=page==item,onClick={page=item},icon={},label={Text(item)}) } } }) { pad -> Column(Modifier.padding(pad).fillMaxSize().padding(16.dp)) {
   when(page){
    "Home" -> { Box(Modifier.fillMaxWidth().background(Maroon,RoundedCornerShape(24.dp)).padding(28.dp)){ Column(horizontalAlignment=Alignment.CenterHorizontally){Text("Your next great idea starts here.",fontSize=27.sp,fontWeight=FontWeight.Bold,color=Color.White); Spacer(Modifier.height(10.dp)); Text("Discover books. Explore new subjects. Grow your knowledge.",color=Color.White); Spacer(Modifier.height(18.dp)); Button(onClick={page="Explore Books"},colors=ButtonDefaults.buttonColors(containerColor=Color.White,contentColor=Maroon)){Text("Explore Library")} } }; Spacer(Modifier.height(18.dp)); Text(status,color=Maroon) }
    "Explore Books" -> { OutlinedTextField(query,{query=it},label={Text("Search title or author")},modifier=Modifier.fillMaxWidth()); Spacer(Modifier.height(12.dp)); Text(status,color=Maroon); LazyColumn { items(books){b-> Card(Modifier.fillMaxWidth().padding(vertical=5.dp),colors=CardDefaults.cardColors(containerColor=Color.White)){Column(Modifier.padding(16.dp)){Text(b.category.uppercase(),color=Maroon,fontSize=11.sp);Text(b.title,fontWeight=FontWeight.Bold,fontSize=18.sp);Text(b.author,color=Color.Gray);Text(b.description.take(130))} } } } }
    "AI Assistant" -> { Text("BrainStack AI Assistant",fontSize=23.sp,fontWeight=FontWeight.Bold,color=Maroon); Spacer(Modifier.height(10.dp)); Text("Connect your configured ElevenLabs Agent ID to enable the embedded voice assistant."); Text("Ask the assistant to search books, retrieve details, compare titles, and recommend reading.",color=Color.Gray) }
    else -> { Text("My Library",fontSize=24.sp,fontWeight=FontWeight.Bold,color=Maroon); Text("Sign in to synchronize favorites and downloads across web and Android.") }
   }
  } }
 }
}
