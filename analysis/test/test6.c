int main(int argc, char** argv){
  if(argc < 3)
here: argc++;
  else
there: argc += 4;
  if(argc > 4) goto here;
  else if(argc > 6) goto there;
  printf("%d\n", argc);
}
